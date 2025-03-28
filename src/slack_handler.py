from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
from dotenv import load_dotenv
from memory import update_global_memory
import logging
import sys

# Set up logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

load_dotenv()

# Log environment variables (excluding sensitive values)
slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
slack_app_token = os.environ.get("SLACK_APP_TOKEN")
slack_channel_id = os.environ.get("SLACK_CHANNEL_ID")

logger.info(f"Slack Channel ID configured: {slack_channel_id}")
logger.info(f"Slack Bot Token present: {'Yes' if slack_bot_token else 'No'}")
logger.info(f"Slack App Token present: {'Yes' if slack_app_token else 'No'}")

# Initialize the Slack app with your bot token
app = App(token=slack_bot_token)

@app.middleware
def log_request(logger, body, next):
    logger.debug(f"Incoming Slack event: {body}")
    return next()

# Listen to all messages
@app.message("")
def handle_all_messages(message, say, logger):
    try:
        logger.debug(f"Received message: {message}")
        
        # Ignore bot messages
        if message.get("bot_id") or message.get("subtype") == "bot_message":
            logger.debug("Ignoring bot message")
            return

        channel_id = message.get("channel")
        text = message.get("text", "")
        user = message.get("user")
        
        logger.info(f"Processing message from {user} in {channel_id}: {text[:50]}...")
        
        if channel_id == slack_channel_id and text:
            logger.info("Updating memory with message")
            update_global_memory(text)
            say(f"✅ Message stored: {text[:50]}...")
            logger.info("Memory updated and confirmation sent")
        else:
            logger.warning(f"Message ignored. Expected channel: {slack_channel_id}, Got: {channel_id}")
            
    except Exception as e:
        logger.exception("Error processing message")
        say("Error processing message. Please try again.")

# Listen to mentions
@app.event("app_mention")
def handle_mentions(body, say, logger):
    try:
        event = body["event"]
        channel_id = event.get("channel")
        text = event.get("text", "")
        logger.info(f"Bot mentioned in {channel_id}: {text}")
        say("I'm here! I'll store any messages sent in this channel.")
    except Exception as e:
        logger.exception("Error handling mention")

def start_slack_handler():
    """Start the Slack event listener"""
    try:
        logger.info("Initializing Slack handler...")
        if not slack_bot_token or not slack_app_token:
            raise ValueError("Missing required Slack tokens")
            
        # Test the tokens before starting
        app.client.auth_test()
        logger.info("Auth test successful")

        # Test channel access
        try:
            result = app.client.conversations_info(channel=slack_channel_id)
            logger.info(f"Successfully connected to channel: {result['channel']['name']}")
        except Exception as e:
            logger.error(f"Cannot access channel {slack_channel_id}: {e}")
            raise
        
        handler = SocketModeHandler(
            app=app,
            app_token=slack_app_token
        )
        
        logger.info("Starting Slack handler...")
        handler.start()
        logger.info("Slack handler started successfully")
        
    except Exception as e:
        logger.exception(f"Failed to start Slack handler: {e}")
        raise 