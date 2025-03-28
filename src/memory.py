import os
import json
from datetime import datetime

MEMORY_FILE = "memory.json"

def load_memory():
    """Load messages from memory file, always reading fresh data"""
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"global": []}

def save_memory(memory):
    """Save messages to memory file immediately"""
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def get_faq_answer(query: str) -> str:
    memory = load_memory()
    # Only check global memory (Slack messages)
    global_messages = memory.get("global", [])
    for message in global_messages:
        if query.lower() in message.lower():
            return message
    return ""

def update_global_memory(message: str):
    """Add a new Slack message to memory with timestamp"""
    memory = load_memory()
    global_messages = memory.get("global", [])
    
    # Add message if it's new
    if message not in global_messages:
        global_messages.append(message)
        # Keep only the last 1000 messages to prevent file from growing too large
        if len(global_messages) > 1000:
            global_messages = global_messages[-1000:]
        memory["global"] = global_messages
        save_memory(memory)
    
    return memory

def clear_memory():
    """Clear all memory except structure"""
    save_memory({"global": []})

# Initialize memory file if it doesn't exist
if not os.path.exists(MEMORY_FILE):
    save_memory({"global": []})
