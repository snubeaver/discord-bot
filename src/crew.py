import os
import yaml
from crewai import Agent, Crew, Task, Process
from memory import get_faq_answer, update_faq_memory
from unanswered import add_unanswered, load_unanswered, remove_answered, reprocess_unanswered
from slack_fallback import notify_slack, notify_unresolved_count

def load_config(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

agents_config = load_config(os.path.join("config", "agents.yaml"))
tasks_config = load_config(os.path.join("config", "tasks.yaml"))

def get_product_knowledge():
    with open(os.path.join("knowledge", "product_info.txt"), "r") as f:
        product_info = f.read()
    with open(os.path.join("knowledge", "announcements.txt"), "r") as f:
        announcements = f.read()
    return product_info + "\n" + announcements

def simulate_agent_answer(query: str) -> str:
    knowledge = get_product_knowledge()
    if query.lower() in knowledge.lower():
        return f"Answer based on product knowledge:\n{knowledge}\n\nYour Query: {query}"
    else:
        return ""  # Unable to confidently answer

def get_answer_with_fallback(query: str, user_id: str) -> dict:
    faq_answer = get_faq_answer(query)
    if faq_answer:
        return {"answer": faq_answer, "uncertain": False}

    answer = simulate_agent_answer(query)
    if answer:
        update_faq_memory(query, answer)
        # If an answer is found, also remove it from the unanswered queue.
        remove_answered(query)
        return {"answer": answer, "uncertain": False}
    else:
        # Add query to unanswered queue.
        add_unanswered(query, user_id)
        # Notify Slack about the new unanswered query.
        notify_slack(query)
        return {"answer": "", "uncertain": True, "slack_answer": None}

def reprocess_unanswered_and_notify() -> int:
    # Recheck unanswered queries against updated knowledge.
    unresolved = reprocess_unanswered()
    # Notify Slack with the current count of unresolved queries.
    notify_unresolved_count(len(unresolved))
    return len(unresolved)
