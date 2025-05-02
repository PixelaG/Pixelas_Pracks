import discord
from discord.ext import commands
from discord import app_commands
import json
import os

TOKEN = os.getenv("DISCORD_TOKEN")  # Render-ზე გამოვიყენებთ env ცვლადს
DATA_FILE = "registered_channels.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def load_channels():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_channels(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot connected as {bot.user}")

@bot.tree.command(name="regchannel", description="დაარეგისტრირე არხი სისტემისთვის")
@app_commands.describe(channel="აირჩიე არხი")
async def regchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    data = load_channels()
    data[str(interaction.guild.id)] = channel.id
    save_channels(data)
    await interaction.response.send_message(f"✅ არხი `{channel.name}` წარმატებით დარეგისტრირდა!", ephemeral=True)

@bot.command()
async def send(ctx, *, message: str):
    data = load_channels()
    channel_id = data.get(str(ctx.guild.id))
    if channel_id:
        channel = ctx.guild.get_channel(channel_id)
        if channel:
            await channel.send(message)
        else:
            await ctx.send("⚠️ არხი ვერ მოიძებნა.")
    else:
        await ctx.send("⚠️ ჯერ არხი არ არის რეგისტრირებული. გამოიყენე /regchannel.")

bot.run(TOKEN)