import os
import re
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
intents.members = True  # აუცილებელია წევრების წვდომისთვის
intents.guilds = True
intents.message_content = True  # აუცილებელია ტექსტური შეტყობინებების წასაკითხად
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        print(f"🔧 Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild_id = message.guild.id
    record = channel_collection.find_one({"guild_id": guild_id})

    if record and "channel_id" in record and message.channel.id == record["channel_id"]:
        try:
            banned_role_id = record["banned_role"]
            banned_role = message.guild.get_role(banned_role_id)

            if banned_role in message.author.roles:
                await message.add_reaction("❌")
                print(f"[INFO] {message.author.name} has banned role, no 22:00 role assigned.")
            else:
                await message.add_reaction("✅")
                role = message.guild.get_role(record["role_22_00"])
                if role:
                    await message.author.add_roles(role)
                    print(f"[INFO] Role {role.name} added to {message.author.name}")
                else:
                    print("[ERROR] 22:00 role not found")

                # შეტყობინების ტექსტის დამატება registered_messages-ში
                channel_collection.update_one(
                    {"guild_id": guild_id},
                    {"$addToSet": {"registered_messages": message.content}},
                    upsert=True
                )
                print(f"[INFO] Message '{message.content}' added to registered_messages.")
        except Exception as e:
            print(f"[ERROR] {e}")
            
    await bot.process_commands(message)

# /regchannel ბრძანება
@bot.tree.command(name="regchannel_22_00", description="დაარეგისტრირე არხი 22:00 როლით")
@app_commands.describe(channel="არხის ID", role_22_00="22:00 როლი", banned_role="Banned როლი", teamlist_channel="Team List არხი")
async def regchannel_22_00(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    role_22_00: discord.Role,
    banned_role: discord.Role,
    teamlist_channel: discord.TextChannel
):
    guild_id = interaction.guild.id

    # MongoDB-ში მონაცემების შენახვა (შედის teamlist_channel.id)
    channel_collection.update_one(
        {"guild_id": guild_id},
        {"$set": {
            "channel_id": channel.id,
            "role_22_00": role_22_00.id,
            "banned_role": banned_role.id,
            "teamlist_channel": teamlist_channel.id
        }},
        upsert=True
    )

    try:
        await interaction.response.send_message(
            f"✅ არხი `{channel.name}` და როლები წარმატებით დარეგისტრირდა MongoDB-ში!\n"
            f"📄 Team List Channel: `{teamlist_channel.name}`"
        )
    except Exception as e:
        print(f"Error sending response: {e}")


@bot.tree.command(name="reg_22_00", description="გამოაგზავნე რეგისტრაციის შეტყობინება")
async def reg_22_00(interaction: discord.Interaction):
    try:
        await interaction.response.defer()  # მხოლოდ ერთხელ უნდა მოხდეს acknowledgment

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
                await interaction.followup.send("✅ რეგისტრაციის შეტყობინება წარმატებით გაიგზავნა!")
            else:
                await interaction.followup.send("⚠️ არხი ვერ მოიძებნა.")
        else:
            await interaction.followup.send("⚠️ ჯერ არხი არ არის რეგისტრირებული. გამოიყენე /regchannel_22:00.")

    except Exception as e:
        print(f"Error sending response: {e}")

@bot.tree.command(name="createteamlist", description="შექმენი Team List 22:00")
async def createteamlist(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    record = channel_collection.find_one({"guild_id": guild_id})

    if not record or "registered_messages" not in record:
        await interaction.response.send_message("⚠️ ჯერ არ არის შეტყობინება რეგისტრირებული.")
        return

    team_channel_id = record.get("teamlist_channel")
    team_channel = interaction.guild.get_channel(team_channel_id)
    if not team_channel:
        await interaction.response.send_message("⚠️ Team List არხი ვერ მოიძებნა.")
        return

    messages = record["registered_messages"]

    # ფორმატირებული ციფრები unicode მრგვალი სტილში (𝟬𝟭, 𝟭𝟬, და ა.შ.)
    def to_fancy_number(n):
        num_map = {'0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵'}
        return ''.join(num_map[d] for d in f"{n:02}")

    lines = [
        f"> {to_fancy_number(i + 1)}. {messages[i]}" if i < len(messages)
        else f"> {to_fancy_number(i + 1)}."
        for i in range(25)
    ]

    message = (
        "> \n"
        ">                  __**TEAM LIST**__\n"
        ">                        **22:00**\n"
        + "\n".join(lines) +
        "\n>\n> || @everyone  ||"
    )

    await team_channel.send(message)
    await interaction.response.send_message("✅ Team List წარმატებით გამოიგზავნა!", ephemeral=True)

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
