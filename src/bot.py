import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from crew import get_answer_with_fallback, reprocess_unanswered_and_notify

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Ensure Message Content Intent is enabled in your Discord Developer Portal.
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    # Ignore bot messages.
    if message.author.bot:
        return

    query = message.content
    user_id = str(message.author.id)

    # Get answer with fallback logic
    result = get_answer_with_fallback(query, user_id)

    if result.get("uncertain"):
        reply = f"Hi {message.author.mention}, thanks for your message. I don't have the answer right now, but I'll be back with an answer shortly!"
        await message.channel.send(reply)
    else:
        await message.channel.send(result.get("answer"))

    # Process commands (if any)
    await bot.process_commands(message)

# Optional command to manually trigger reprocessing of unanswered queries.
@bot.command(name="reprocess")
async def manual_reprocess(ctx):
    unresolved = reprocess_unanswered_and_notify()
    await ctx.send(f"Reprocessed unanswered queries. Currently unresolved: {unresolved}")

bot.run(DISCORD_BOT_TOKEN)
