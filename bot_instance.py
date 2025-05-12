import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True  
intents.guilds = True
intents.message_content = True 
intents.messages = True

bot = commands.Bot(command_prefix="p!", intents=intents, help_command=None)
