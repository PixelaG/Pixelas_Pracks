import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
import os

TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGODB_URI")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# MongoDB კავშირი
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["discord_bot"]
channel_collection = db["registered_channels"]

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
    await interaction.response.send_message(f"✅ არხი `{channel.name}` წარმატებით დარეგისტრირდა ყველასთვის 🎉")

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
