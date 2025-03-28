import os
import asyncio
import discord
import threading
import logging
from discord.ext import commands
from dotenv import load_dotenv
from crew import get_answer_with_fallback, reprocess_unanswered_and_notify, periodic_recheck_unanswered
from memory import update_global_memory
from slack_fallback import notify_slack
from slack_handler import start_slack_handler

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALLOWED_CHANNEL_ID = "1355067647292866622"

# Set up the bot with minimal intents needed
intents = discord.Intents.default()
intents.message_content = True

# Initialize the bot without a command prefix
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Untitled Bank Bot is ready! Logged in as {bot.user}")
    # Start the periodic recheck of unanswered questions
    bot.loop.create_task(periodic_recheck_unanswered())
    
    try:
        # Start Slack handler in a separate thread
        slack_thread = threading.Thread(target=start_slack_handler, daemon=True)
        slack_thread.start()
        logger.info("Slack handler thread started")
    except Exception as e:
        logger.error(f"Failed to start Slack handler: {e}")

@bot.event
async def on_message(message: discord.Message):
    # Ignore messages from bots (including itself)
    if message.author.bot:
        return

    # Check if the message is in the allowed channel
    if str(message.channel.id) != ALLOWED_CHANNEL_ID:
        return

    query = message.content
    user_id = str(message.author.id)

    # Optional: Add typing indicator to make it feel more natural
    async with message.channel.typing():
        # Process the query and check for a confident answer
        result = get_answer_with_fallback(query, user_id)

        if result.get("uncertain"):
            reply = f"Hi {message.author.mention}, thanks for your question about Untitled Bank. I'll need to check on that and get back to you shortly!"
            await message.channel.send(reply)
            # Notify Slack without storing in memory
            notify_slack(f"New question from Discord: {query}")
        else:
            await message.channel.send(result.get("answer"))

bot.run(DISCORD_BOT_TOKEN)
