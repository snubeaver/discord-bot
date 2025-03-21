import os
import json

MEMORY_FILE = "memory.json"

def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)

def get_faq_answer(query: str) -> str:
    memory = load_memory()
    return memory.get(query, "")

def update_faq_memory(query: str, answer: str):
    memory = load_memory()
    memory[query] = answer
    save_memory(memory)
