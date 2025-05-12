from discord.ext import commands
from discord import Intents

intents = Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
