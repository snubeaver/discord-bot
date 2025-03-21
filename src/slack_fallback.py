import os
import requests
from dotenv import load_dotenv

load_dotenv()

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def notify_slack(query: str):
    if not SLACK_WEBHOOK_URL:
        print("No Slack webhook URL configured.")
        return
    message = {
        "text": f"New unanswered query received: '{query}'. Please update the knowledge base if possible."
    }
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message)
        if response.status_code != 200:
            print(f"Slack notification failed: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Error notifying Slack: {e}")

def notify_unresolved_count(count: int):
    if not SLACK_WEBHOOK_URL:
        print("No Slack webhook URL configured.")
        return
    message = {
        "text": f"Current unresolved queries count: {count}. Please review these questions in the knowledge base."
    }
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message)
        if response.status_code != 200:
            print(f"Slack unresolved count notification failed: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Error notifying Slack: {e}")
