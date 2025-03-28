import os
import yaml
import asyncio
from crewai import Agent, Crew, Task, Process
from memory import load_memory
from unanswered import add_unanswered, load_unanswered, remove_answered, reprocess_unanswered
from slack_fallback import notify_slack, notify_unresolved_count
from langchain_openai import ChatOpenAI
from typing import List, Tuple, Dict

# Define category keywords at module level
CATEGORY_KEYWORDS = {
    'core_bank': ['core bank', 'dao', 'deposit', 'lending'],
    'custom_bank': ['custom bank', 'risk', 'operator'],
    'market': ['market', 'liquidity', 'trading', 'borrow'],
    'features': ['multiply', 'leverage', 'bundle', 'transaction'],
    'assets': ['asset', 'token', 'defi', 'long-tail'],
    'announcements': ['update', 'new', 'announcement', 'change'],
    'general': ['bank', 'untitled', 'help', 'what', 'how', 'why', 'when', 'where']  # Added general keywords
}

# Comprehensive agent role and background
AGENT_PERSONA = """
You are an Intern at Untitled Bank, Untitled Bank's Product Specialist and AI Assistant. Your core responsibilities include:

ROLE & EXPERTISE:
1. Deep Technical Knowledge
- Expert in DeFi lending platforms and protocols
- Specialist in Untitled Bank's unique Layered Bank architecture
- Understanding of both simple and complex DeFi concepts

2. Communication Style
- Clear and approachable explanations for both beginners and experts
- Professional yet friendly tone
- Ability to adjust technical depth based on the question context

3. Problem-Solving Approach
- Analyze questions from multiple angles
- Connect relevant concepts across different features
- Provide comprehensive answers with practical examples
- Consider both immediate solutions and long-term implications

4. Key Responsibilities
- Guide users through Untitled Bank's features
- Explain complex DeFi concepts in accessible terms
- Keep track of latest updates and announcements
- Provide accurate, context-aware responses

INTERACTION GUIDELINES:
1. Always start by understanding the full context of the question
2. Draw connections between different aspects of Untitled Bank
3. Include relevant examples or use cases when helpful
4. Acknowledge both advantages and limitations
5. Provide next steps or additional resources when appropriate
6. If you need more context, don't hesitate to ask for clarification.

PRIORITY AREAS:
1. User Experience & Accessibility
2. Risk Management & Security
3. Technical Accuracy
4. Practical Implementation
5. Current Updates & Changes
"""

# System context that defines what Untitled Bank is
SYSTEM_CONTEXT = """
Untitled Bank is a permissionless, modular lending platform that:
1. Uses an Aggregated and Layered Bank architecture
2. Combines the simplicity of monolithic platforms with the flexibility of modular lending
3. Features Core Bank (managed by DAO) and Custom Banks (operated independently)
4. Supports both key DeFi assets and carefully selected long-tail assets
5. Focuses on capital efficiency and risk management
6. Provides features like Multiply (leverage) and bundled transactions

Key Components:
- Core Bank: Simplified deposit and lending managed by DAO
- Custom Banks: Flexible, configurable risk levels for advanced users
- Core Market: Aggregates markets with identical collateral-loan pairs
- Layered Market Structure: Solves liquidity fragmentation issues
"""

def load_config(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

agents_config = load_config(os.path.join("config", "agents.yaml"))
tasks_config = load_config(os.path.join("config", "tasks.yaml"))

llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.7)

def get_product_knowledge():
    try:
        with open(os.path.join("knowledge", "product_info.txt"), "r", encoding='utf-8') as f:
            product_info = f.read()
        with open(os.path.join("knowledge", "announcements.txt"), "r", encoding='utf-8') as f:
            announcements = f.read()
        return product_info + "\n" + announcements
    except Exception as e:
        print(f"Error reading knowledge files: {e}")
        return ""

def categorize_query(query: str) -> List[str]:
    """
    Categorize the query to determine which aspects of the system it relates to
    """
    categories = []
    query_lower = query.lower()
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in query_lower for keyword in keywords):
            categories.append(category)
    
    return categories or ['general']

def search_knowledge_base(query: str, knowledge: str, categories: List[str]) -> List[Tuple[str, float, str]]:
    """
    Search the knowledge base and return relevant paragraphs with confidence scores and categories
    """
    query = query.lower()
    sections = knowledge.split('\n\n')
    
    relevant_info = []
    
    for section in sections:
        if not section.strip():
            continue
            
        # Calculate basic relevance
        query_words = set(query.split())
        section_words = set(section.lower().split())
        matching_words = query_words.intersection(section_words)
        base_confidence = len(matching_words) / len(query_words) if query_words else 0
        
        # Boost confidence for categorical matches
        category_boost = 0.0
        section_lower = section.lower()
        
        # Handle category matching with fallback to general
        for category in categories:
            if category in CATEGORY_KEYWORDS:
                if any(keyword in section_lower for keyword in CATEGORY_KEYWORDS[category]):
                    category_boost += 0.2  # 20% boost per matching category
        
        final_confidence = min(1.0, base_confidence + category_boost)
        
        if final_confidence > 0.2:
            # Determine the section category with better fallback handling
            section_category = 'general'
            for cat, keywords in CATEGORY_KEYWORDS.items():
                if any(keyword in section_lower for keyword in keywords):
                    section_category = cat
                    break
            relevant_info.append((section, final_confidence, section_category))
    
    # Sort by confidence and return top results, ensuring diverse categories
    relevant_info.sort(key=lambda x: x[1], reverse=True)
    
    # Ensure we have at least one item from each relevant category if available
    final_selection = []
    used_categories = set()
    
    # First, add highest confidence item from each category
    for info in relevant_info:
        if info[2] not in used_categories and len(final_selection) < 5:
            final_selection.append(info)
            used_categories.add(info[2])
    
    # Then add remaining high-confidence items up to 5 total
    for info in relevant_info:
        if info not in final_selection and len(final_selection) < 5:
            final_selection.append(info)
    
    return final_selection

def is_casual_chat(query: str) -> bool:
    """Use LLM to determine if the query is a casual conversation"""
    prompt = f"""Determine if this message is a casual conversation or a product-related question.

Message: "{query}"

Rules:
1. Casual conversations include:
   - Greetings (hi, hello, hey)
   - Small talk (how are you, good morning)
   - Jokes or fun requests
   - Thank you messages
   - General chitchat
   - Emojis or expressions of emotion

2. Product-related questions include:
   - Questions about features or functionality
   - Technical inquiries
   - How-to questions
   - Status inquiries
   - Support requests

Respond with either "casual" or "product" only.

Response:"""

    try:
        llm.temperature = 0.1  # Keep it consistent
        response = llm.invoke(prompt).content.strip().lower()
        return response == "casual"
    except Exception as e:
        print(f"Error in casual chat detection: {e}")
        # If there's an error, default to treating it as a product question
        return False

def get_casual_response(query: str) -> str:
    """Generate contextual casual responses using LLM"""
    prompt = f"""Generate a friendly, casual response to this message. Be brief, fun, and natural.

Message: "{query}"

Guidelines:
1. Keep it short and friendly
2. Use appropriate emojis
3. Stay in character as a helpful banking assistant
4. If it's a joke request, make a light banking/finance pun
5. Match the tone of the input

Response:"""

    try:
        llm.temperature = 0.7  # Allow for more creativity in casual responses
        response = llm.invoke(prompt).content.strip()
        llm.temperature = 0.1  # Reset temperature
        return response
    except Exception as e:
        print(f"Error generating casual response: {e}")
        return "Hey there! 👋 How can I help you today?"

def evaluate_answer_confidence(query: str, answer: str, source_info: List[Tuple[str, float, str]]) -> float:
    """Use LLM to evaluate answer confidence considering DeFi and community context"""
    context = "\n".join([info[0] for info in source_info])
    
    prompt = f"""Evaluate if this answer is appropriate for a DeFi project's community support.

Question: "{query}"
Proposed Answer: "{answer}"
Source Information: "{context}"

Evaluation Criteria:
1. Answer Accuracy (based on source information)
2. DeFi Context Appropriateness:
   - Is this a sensitive topic? (e.g., funds, investments, tokens)
   - Could wrong information cause issues?
3. Community Impact:
   - Does it help the user?
   - Is it clear and direct?
   - Does it maintain trust?

Rate confidence from 0 to 1 based on:
- 1.0: Perfect answer with verified information
- 0.8: Good answer that helps user but might need minor details
- 0.5: Basic answer that's technically correct but might need more context
- 0.3: Answer that might be misleading or incomplete
- 0.0: Wrong or potentially harmful answer

Respond with only a number between 0 and 1.

Response:"""

    try:
        llm.temperature = 0.1
        response = llm.invoke(prompt).content.strip()
        confidence = float(response)
        return min(1.0, max(0.0, confidence))
    except Exception as e:
        print(f"Error in confidence evaluation: {e}")
        return 0.0

def format_answer(query: str, relevant_info: List[Tuple[str, float, str]], source: str) -> Tuple[str, float]:
    """Format the answer and return with confidence score"""
    context = "\n".join([info[0] for info in relevant_info])
    
    prompt = f"""You are Untitled Bank's assistant. Be direct and concise.

CONTEXT:
{context}

Question: "{query}"

Instructions:
1. Answer ONLY the specific question asked
2. Keep the response under 2 sentences
3. Be direct and clear
4. For sensitive topics (funds, tokens, airdrop), be extra clear
5. If there's a link, just say "Here's how to [action]: [link]"
6. Don't add unnecessary information

Response:"""

    try:
        llm.temperature = 0.1
        answer = llm.invoke(prompt).content.strip()
        
        # Evaluate confidence
        confidence = evaluate_answer_confidence(query, answer, relevant_info)
        
        return answer, confidence
    except Exception as e:
        print(f"Error generating response: {e}")
        return "", 0.0

def check_memory_for_answer(query: str) -> List[Tuple[str, float, str]]:
    """
    Check memory for relevant Slack messages, prioritizing recent ones
    """
    memory = load_memory()
    if not memory:
        return []

    relevant_info = []
    query_lower = query.lower()
    
    # Define main topics and their related terms, including crypto slang
    topics = {
        "wallet": ["wallet", "connect", "address"],
        "twitter": ["twitter", "social", "tweet"],
        "points": ["point", "reward", "earn"],
        "card": ["card", "upgrade"],
        "withdraw": ["withdraw", "fund"],
        "airdrop": ["airdrop", "wen", "when airdrop", "drop"],
        "error": ["error", "can't", "cannot", "issue", "problem"]
    }
    
    # Common crypto slang replacements
    slang_map = {
        "wen": "when",
        "ser": "sir",
        "gm": "good morning",
        "wagmi": "we are going to make it"
    }
    
    # Preprocess query to handle slang
    for slang, formal in slang_map.items():
        query_lower = query_lower.replace(slang, formal)
    
    # Identify the query topic
    query_topic = None
    for topic, keywords in topics.items():
        if any(keyword in query_lower for keyword in keywords):
            query_topic = topic
            break
    
    # Check messages in reverse order (newest first)
    for message in reversed(memory.get("global", [])):
        message_lower = message.lower()
        
        # If we found a topic match, only look for messages about that topic
        if query_topic:
            if any(keyword in message_lower for keyword in topics[query_topic]):
                # For airdrop questions, combine relevant messages
                if query_topic == "airdrop":
                    airdrop_messages = [msg for msg in memory.get("global", []) 
                                     if "airdrop" in msg.lower()]
                    if airdrop_messages:
                        combined_message = " | ".join(airdrop_messages)
                        relevant_info.append((combined_message, 1.0, 'exact'))
                        break
                else:
                    relevant_info.append((message, 1.0, 'exact'))
                    break
        else:
            # For queries without a clear topic, use word matching
            query_words = set(query_lower.split())
            message_words = set(message_lower.split())
            matching_words = query_words.intersection(message_words)
            
            if matching_words:
                word_match_score = len(matching_words) / len(query_words) if query_words else 0
                if word_match_score > 0.5:
                    relevant_info.append((message, word_match_score, 'general'))
    
    return relevant_info[:1]  # Limit to 1 most relevant message

def simulate_agent_answer(query: str) -> Tuple[str, float]:
    # Always check memory first
    memory_results = check_memory_for_answer(query)
    if memory_results:
        return format_answer(query, memory_results, "memory")
    
    # Only if no memory matches, check knowledge base
    knowledge = get_product_knowledge()
    if knowledge:
        knowledge_results = search_knowledge_base(query, knowledge, categorize_query(query))
        if knowledge_results:
            return format_answer(query, knowledge_results, "knowledge")
    
    return "", 0.0

def get_answer_with_fallback(query: str, user_id: str) -> dict:
    # First check if it's a casual conversation using LLM
    if is_casual_chat(query):
        casual_response = get_casual_response(query)
        return {"answer": casual_response, "uncertain": False}
    
    # If not casual, proceed with normal flow
    answer, confidence = simulate_agent_answer(query)
    
    # Handle response based on confidence
    if confidence >= 0.8:  # High confidence
        return {"answer": answer, "uncertain": False}
    elif confidence >= 0.5:  # Medium confidence
        return {"answer": f"{answer}\n\nNote: Feel free to ask in our Discord if you need more details.", "uncertain": False}
    elif answer and confidence > 0:  # Low confidence but have some answer
        add_unanswered(query, user_id)
        notify_slack(f"Low confidence answer provided for: {query}")
        return {"answer": "I might not have the complete information. The team will provide more details, but here's what I know: " + answer, "uncertain": True}
    else:  # No confidence or no answer
        add_unanswered(query, user_id)
        notify_slack(query)
        return {"answer": "The team will be here shortly to help you with this question.", "uncertain": True}

async def periodic_recheck_unanswered():
    """
    Periodically recheck unanswered questions and update memory with new information
    """
    while True:
        unanswered = load_unanswered()
        memory = load_memory()
        global_messages = memory.get("global", [])
        
        # Check if there are new answers in global memory for unanswered questions
        for query, info in unanswered.items():
            # First try to find a direct answer from memory
            for message in global_messages:
                if query.lower() in message.lower():
                    remove_answered(query)
                    # Send confirmation to Slack
                    notify_slack(f"Found answer in Slack for: {query}")
                    break
            
            # If no direct match, try normal answer generation
            answer, confidence = simulate_agent_answer(query)
            if answer:
                remove_answered(query)
                # Send confirmation to Slack
                notify_slack(f"Generated answer for: {query}")
        
        await asyncio.sleep(300)  # Check every 5 minutes

def reprocess_unanswered_and_notify() -> int:
    unresolved = reprocess_unanswered()
    notify_unresolved_count(len(unresolved))
    return len(unresolved)
