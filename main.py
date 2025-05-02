import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
from pymongo import MongoClient 
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    thread = Thread(target=run_flask)
    thread.daemon = True
    thread.start()

keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
mongo_uri = os.getenv("MONGO_URI")

# MongoDB კავშირი 
client = MongoClient(mongo_uri)
db = client["Pixelas_Pracks"]
channel_collection = db["registered_channels"]

intents = discord.Intents.default()
intents.message_content = True  # აუცილებელია ტექსტური შეტყობინებების წასაკითხად
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot connected as {bot.user}")

# /regchannel ბრძანება
@bot.tree.command(name="regchannel", description="დაარეგისტრირე არხი სისტემისთვის")
@app_commands.describe(channel="აირჩიე არხი")
async def regchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = interaction.guild.id
    # შეინახე ან განაახლე მონაცემი
    channel_collection.update_one(
        {"guild_id": guild_id},
        {"$set": {"channel_id": channel.id}},
        upsert=True
    )

    try:
        # შეცვლილია ამ ნაწილში
        await interaction.response.send_message(f"✅ არხი `{channel.name}` წარმატებით დარეგისტრირდა ყველასთვის 🎉")
    except Exception as e:
        print(f"Error sending response: {e}")

# მაგალითი გამოყენების
@bot.command()
async def send(ctx, *, message: str):
    guild_id = ctx.guild.id
    record = channel_collection.find_one({"guild_id": guild_id})

    if record and "channel_id" in record:
        channel = ctx.guild.get_channel(record["channel_id"])
        if channel:
            await channel.send(message)
        else:
            await ctx.send("⚠️ არხი ვერ მოიძებნა.")
    else:
        await ctx.send("⚠️ ჯერ არხი არ არის რეგისტრირებული. გამოიყენე /regchannel.")

bot.run(TOKEN)
