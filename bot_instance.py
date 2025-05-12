import os
import re
import time
import discord
import asyncio
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands, Intents
from flask import Flask
from threading import Thread
from colorama import init, Fore
from datetime import datetime, timedelta
from pymongo import MongoClient

intents = Intents.all()
bot = commands.Bot(command_prefix="p!", intents=intents)
