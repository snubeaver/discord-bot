import os
import json

UNANSWERED_FILE = "unanswered.json"

def load_unanswered():
    try:
        with open(UNANSWERED_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_unanswered(queue):
    with open(UNANSWERED_FILE, "w") as f:
        json.dump(queue, f)

def add_unanswered(query: str, user_id: str):
    queue = load_unanswered()
    # Use query text as key; store user id and query.
    if query not in queue:
        queue[query] = {"user_id": user_id, "query": query}
    save_unanswered(queue)

def remove_answered(query: str):
    queue = load_unanswered()
    if query in queue:
        del queue[query]
        save_unanswered(queue)

def reprocess_unanswered():
    # Reprocess all unanswered queries.
    queue = load_unanswered()
    unresolved = {}
    from crew import simulate_agent_answer, update_faq_memory
    for query, info in queue.items():
        answer = simulate_agent_answer(query)
        if answer:
            update_faq_memory(query, answer)
            # Remove answered query.
            remove_answered(query)
        else:
            unresolved[query] = info
    return unresolved
