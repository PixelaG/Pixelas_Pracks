import os
import time
import discord
import asyncio
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
from flask import Flask
from threading import Thread
from colorama import init, Fore
from datetime import datetime, timedelta
from pymongo import MongoClient 

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
@bot.tree.command(name="regchannel_22_00", description="დაარეგისტრირე არხი და როლები")
@app_commands.describe(channel_id="ჩაწერე არხის ID", role_22_00="ჩაწერე 22:00 როლი", banned_role="ჩაწერე Banned როლი")
async def regchannel_22_00(interaction: discord.Interaction, channel_id: int, role_22_00: int, banned_role: int):
    guild_id = interaction.guild.id
    channel = interaction.guild.get_channel(channel_id)
    role_22_00 = interaction.guild.get_role(role_22_00)
    banned_role = interaction.guild.get_role(banned_role)

    if not channel:
        await interaction.response.send_message("⚠️ არხი ვერ მოიძებნა.")
        return
    if not role_22_00:
        await interaction.response.send_message("⚠️ 22:00 როლი ვერ მოიძებნა.")
        return
    if not banned_role:
        await interaction.response.send_message("⚠️ Banned როლი ვერ მოიძებნა.")
        return

    # MongoDB-ში მონაცემების შენახვა
    channel_collection.update_one(
        {"guild_id": guild_id},
        {
            "$set": {
                "channel_id": channel.id,
                "role_22_00_id": role_22_00.id,
                "banned_role_id": banned_role.id
            }
        },
        upsert=True
    )

    await interaction.response.send_message(f"✅ არხი `{channel.name}` და როლები წარმატებით დარეგისტრირდა.")


@bot.tree.command(name="reg_22_00", description="გამოაგზავნე რეგისტრაციის შეტყობინება")
async def reg_22_00(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    record = channel_collection.find_one({"guild_id": guild_id})

    if record and "channel_id" in record:
        channel = interaction.guild.get_channel(record["channel_id"])
        if channel:
            message = (
                ">>> #  __**Registration is Open**__\n\n"
                "🇬🇪 **22:00**﹒:flag_eu: 🇩🇿 **19:00**\n"
                "__`𝗔𝗱𝘃𝗮𝗻𝗰𝗲𝗱 𝗿𝗼𝗼𝗺 { 𝟯𝘅 𝗹𝗼𝗼𝗧.}`__\n"
                "||@everyone @here ||"
            )
            await channel.send(message)
            await interaction.response.send_message("✅ რეგისტრაციის შეტყობინება წარმატებით გაიგზავნა!")
        else:
            await interaction.response.send_message("⚠️ არხი ვერ მოიძებნა.")
    else:
        await interaction.response.send_message("⚠️ ჯერ არხი არ არის რეგისტრირებული. გამოიყენე /regchannel_22:00.")
        

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
