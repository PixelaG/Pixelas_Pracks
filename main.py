import os
import re
import time
import discord
import asyncio
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
from colorama import init, Fore
from datetime import datetime, timedelta
from pymongo import MongoClient 
from PIL import ImageFont, ImageDraw, Image
import requests
import io

load_dotenv()

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


client = MongoClient(mongo_uri)
db = client["Pixelas_Pracks"]
channel_collection = db["registered_channels"]
access_entries = db["access_entries"]
teams_collection = db["Teams"]


intents = discord.Intents.default()
intents.members = True  
intents.guilds = True
intents.message_content = True 
intents.messages = True
bot = commands.Bot(command_prefix="p!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"✅ Bot connected as {bot.user}")
    bot.loop.create_task(check_expired_access())
    await bot.change_presence(status=discord.Status.invisible)
    
    try:
        now = datetime.utcnow()
        await bot.change_presence(
        activity=discord.Game(name="PUBG Mobile 🎮")
    )
            
        for entry in active_entries:
            guild = bot.get_guild(entry["guild_id"])
            if not guild:
                continue
                
            try:
                member = await guild.fetch_member(entry["user_id"])
                role = guild.get_role(entry["role_id"])
                
                if role and member and role not in member.roles:
                    await member.add_roles(role)
                    print(f"აღდგენილი როლი: {member.display_name} -> {role.name}")
            except:
                continue
    
    except Exception as e:
        print(f"შეცდომა როლების აღდგენისას: {e}")
    
    try:
        await bot.tree.sync()
        print(Fore.GREEN + "✅ Slash commands synced successfully.")
    except Exception as e:
        print(Fore.RED + f"❌ Failed to sync commands: {e}")


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    await asyncio.sleep(0.5)  # დროებითი დაყოვნება
    guild_id = message.guild.id
    record = channel_collection.find_one({"guild_id": guild_id})

    try:
        if record:
            banned_role_id = record.get("banned_role")
            banned_role = message.guild.get_role(banned_role_id)

            # რეაქციის ემოჯები
            deny_emoji = record.get("custom_react_emoji_deny", "❌")
            allow_emoji = record.get("custom_react_emoji_allow", "✅")

            # რეგისტრაციის არხების სია
            registration_channels = [
                record.get("channel_id_19_00"),
                record.get("channel_id_22_00"),
                record.get("channel_id_00_30")
            ]

            if banned_role and banned_role in message.author.roles:
                if message.channel.id in registration_channels:
                    await asyncio.sleep(15)
                    await message.add_reaction(deny_emoji)  # ✅ დაამატე რეაქცია აქ
            else:
                pattern = r"^[^\n]+[ /|][^\n]+[ /|]<@!?[0-9]+>$"
                match = re.match(pattern, message.content.strip())

                if match:
                    time_slots = ["19_00", "22_00", "00_30"]

                    for slot in time_slots:
                        channel_key = f"channel_id_{slot}"
                        role_key = f"role_{slot}"
                        messages_key = f"registered_messages_{slot.replace('_', ':')}"

                        if channel_key in record and message.channel.id == record[channel_key]:
                            await asyncio.sleep(15)
                            role = message.guild.get_role(record.get(role_key))

                            if role:
                                await message.author.add_roles(role)
                                await message.add_reaction(allow_emoji)  # ✅ დაამატე რეაქცია აქ

                            # MongoDB განახლება
                            channel_collection.update_one(
                                {"guild_id": guild_id},
                                {"$addToSet": {messages_key: {
                                    "message_id": message.id,
                                    "user_id": message.author.id,
                                    "content": message.content
                                }}},
                                upsert=True
                            )
                            break
    except Exception as e:
        print(f"[ERROR] {e}")

    await bot.process_commands(message)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or not after.guild:
        return

    guild_id = after.guild.id
    record = channel_collection.find_one({"guild_id": guild_id})

    try:
        if record:
            banned_role_id = record.get("banned_role")
            banned_role = after.guild.get_role(banned_role_id)

            if banned_role and banned_role in after.author.roles:
                await after.add_reaction("❌")
            else:
                # მხოლოდ თუ შეტყობინების ფორმატი შეცვლილია
                pattern = r"^[^\n]+[ /|][^\n]+[ /|]<@!?[0-9]+>$"
                if re.match(pattern, after.content.strip()):
                    # ახალი შეტყობინება განახლდება TeamList-ში
                    time_slots = ["19_00", "22_00", "00_30"]

                    for slot in time_slots:
                        channel_key = f"channel_id_{slot}"
                        messages_key = f"registered_messages_{slot.replace('_', ':')}"

                        if channel_key in record and after.channel.id == record[channel_key]:
                            # MongoDB განახლება
                            channel_collection.update_one(
                                {"guild_id": guild_id},
                                {"$pull": {messages_key: {"message_id": before.id}}},  # ძველი შეტყობინების ამოშლა
                                upsert=True
                            )
                            channel_collection.update_one(
                                {"guild_id": guild_id},
                                {"$addToSet": {messages_key: {
                                    "message_id": after.id,
                                    "user_id": message.author.id,
                                    "content": after.content
                                }}},
                                upsert=True
                            )
                            break  # გავჩერდეთ როცა შესაბამის არხზე ვიპოვით ემთხვევას

    except Exception as e:
        print(f"[ERROR] {e}")



@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild:
        return

    guild_id = message.guild.id
    record = channel_collection.find_one({"guild_id": guild_id})
    if not record:
        return

    time_slots = [
        ("22:00", "channel_id_22_00", "role_22_00", "registered_messages_22:00"),
        ("19:00", "channel_id_19_00", "role_19_00", "registered_messages_19:00"),
        ("00:30", "channel_id_00_30", "role_00_30", "registered_messages_00:30"),
    ]

    for label, channel_field, role_field, messages_field in time_slots:
        if channel_field in record and message.channel.id == record[channel_field]:
            registered_messages = record.get(messages_field, [])
            updated_messages = [m for m in registered_messages if m["message_id"] != message.id]

            if len(updated_messages) != len(registered_messages):
                # ამოღება TeamList-დან
                channel_collection.update_one(
                    {"guild_id": guild_id},
                    {"$set": {messages_field: updated_messages}}
                )

                # ჩამოართვას როლი
                role = message.guild.get_role(record[role_field])
                if role:
                    member = message.guild.get_member(message.author.id)
                    if member and role in member.roles:
                        await member.remove_roles(role)
                        print(f"Removed role {role.name} from {member.name} for {label} due to message deletion.")
        

async def check_expired_access():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.utcnow()
        expired_entries = access_entries.find({"expiry_time": {"$lte": now}, "is_active": True})

        for entry in expired_entries:
            user_id = entry["user_id"]
            guild_id = entry["guild_id"]
            role_id = entry["role_id"]
            log_channel_id = entry.get("log_channel_id")
            
            main_guild = bot.get_guild(MAIN_SERVER_ID)
            if not main_guild:
                continue

            try:
                member = await main_guild.fetch_member(user_id)
                role = main_guild.get_role(role_id)

                if member and role:
                    await member.remove_roles(role)
            except discord.NotFound:
                pass
            except discord.Forbidden:
                pass
            except Exception as e:
                print(f"Error removing role from user {user_id}: {e}")

            # remove from database
            access_entries.delete_one({"_id": entry["_id"]})

            # log expiry
            if log_channel_id:
                log_channel = main_guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="⌛ წვდომის ვადა ამოიწურა",
                        description=f"🎖 <@{user_id}>-ს წვდომის დრო ამოიწურა",
                        color=discord.Color.red()
                    )
                    embed.set_footer(text="Pixelas Access System")
                    await log_channel.send(embed=embed)

            # now check if this guild has no more valid entries
            remaining = access_entries.count_documents({"guild_id": guild_id})
            if remaining == 0:
                guild = bot.get_guild(guild_id)
                if guild:
                    try:
                        await guild.leave()
                        print(f"🛫 ბოტი გავიდა სერვერიდან: {guild.name}")
                    except Exception as e:
                        print(f"Could not leave guild {guild_id}: {e}")
        
        await asyncio.sleep(500)  # ყოველ 5 წუთსი ამოწმებს
        

async def send_embed_notification(interaction, title, description, color=discord.Color(0x2f3136)):
    embed = discord.Embed(title=title, description=description, color=color)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.NotFound:
        print("⚠ Interaction უკვე ამოიწურა ან გაუქმდა.")
    except discord.HTTPException as e:
        print(f"⚠ HTTP შეცდომა Embed-ის გაგზავნისას: {e}")
        

async def check_user_permissions(interaction, required_role_id: int, guild_id: int):
    home_guild = discord.utils.get(bot.guilds, id=guild_id)
    if not home_guild:
        await send_embed_notification(interaction, "⚠️ მთავარი სერვერი არ არის ნაპოვნი", "⌚️ სცადეთ მოგვიანებით.")
        return None

    try:
        member = await home_guild.fetch_member(interaction.user.id)
    except discord.NotFound:
        await send_embed_notification(
            interaction,
            "⛔️ თქვენ არ ხართ მთავარ სერვერზე",
            "🌐 შემოგვიერთდით ახლავე [Server](https://discord.gg/byScSM6T9Q)"
        )
        return None

    if not any(role.id == required_role_id for role in member.roles):
        await send_embed_notification(
            interaction,
            "🚫 თქვენ არ შეგიძლიათ ამ ფუნქციის გამოყენება",
            "💸 შესაძენად ეწვიეთ სერვერს [Server](https://discord.gg/byScSM6T9Q) 💸"
        )
        return None

    return member



async def check_user_permissions_for_ctx(ctx, required_role_id: int, guild_id: int):
    home_guild = discord.utils.get(bot.guilds, id=guild_id)
    if not home_guild:
        await ctx.send("⚠️ მთავარი სერვერი არ არის ნაპოვნი. სცადეთ მოგვიანებით.")
        return None

    try:
        member = await home_guild.fetch_member(ctx.author.id)
    except discord.NotFound:
        await ctx.send("⛔️ თქვენ არ ხართ მთავარ სერვერზე. შემოგვიერთდით: https://discord.gg/byScSM6T9Q")
        return None

    if not any(role.id == required_role_id for role in member.roles):
        await ctx.send("🚫 თქვენ არ გაქვთ ამ ქომანდის გამოყენების უფლება. შესაძენად ეწვიეთ სერვერს: https://discord.gg/byScSM6T9Q")
        return None

    return member

# 19:00 SETUP
@bot.tree.command(name="regchannel_19_00", description="დაარეგისტრირე არხი 19:00 როლით")
@app_commands.describe(channel="არხის ID", role_19_00="19:00 როლი", banned_role="Banned როლი", teamlist_channel="Team List არხი")
@app_commands.checks.has_permissions(administrator=True)
async def regchannel_19_00(interaction: discord.Interaction, channel: discord.TextChannel, role_19_00: discord.Role, banned_role: discord.Role, teamlist_channel: discord.TextChannel):

    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
       return
    
    guild_id = interaction.guild.id

    channel_collection.update_one(
        {"guild_id": guild_id},
        {"$set": {
            "channel_id_19_00": channel.id,
            "role_19_00": role_19_00.id,
            "banned_role": banned_role.id,
            "teamlist_channel_19:00": teamlist_channel.id
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


@bot.tree.command(name="reg_19_00", description="გამოაგზავნე რეგისტრაციის შეტყობინება")
@app_commands.checks.has_permissions(administrator=True)
async def reg_19_00(interaction: discord.Interaction):

    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
       return
    
    try:
        await interaction.response.defer()  

        guild_id = interaction.guild.id
        record = channel_collection.find_one({"guild_id": guild_id})

        if record and "channel_id_19_00" in record:
            channel = interaction.guild.get_channel(record["channel_id_19_00"])
            if channel:
                message = (
                    ">>> #  __**Registration is Open**__\n\n"
                    "🇬🇪 **19:00**﹒:flag_eu: 🇩🇿 **19:00**\n"
                    "__`𝗔𝗱𝘃𝗮𝗻𝗰𝗲𝗱 𝗿𝗼𝗼𝗺 { 𝟯𝘅 𝗹𝗼𝗼𝗧.}`__\n"
                    "||@everyone @here ||"
                )
                await channel.send(message)
                await interaction.followup.send("✅ რეგისტრაციის შეტყობინება წარმატებით გაიგზავნა!")
            else:
                await interaction.followup.send("⚠️ არხი ვერ მოიძებნა.")
        else:
            await interaction.followup.send("⚠️ ჯერ არხი არ არის რეგისტრირებული. გამოიყენე /regchannel_19:00.")

    except Exception as e:
        print(f"Error sending response: {e}")

@bot.tree.command(name="createteamlist_19_00", description="შექმნის Team List 19:00")
@app_commands.checks.has_permissions(administrator=True)
async def createteamlist_19_00(interaction: discord.Interaction):
    try:
        member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
        if not member:
            return

        guild_id = interaction.guild.id
        record = channel_collection.find_one({"guild_id": guild_id})

        if not record or "registered_messages_19:00" not in record:
            await interaction.response.send_message("⚠️ ჯერ არავინ არ არის დარეგისტრირებული 19:00-ზე.", ephemeral=True)
            return

        team_channel_id = record.get("teamlist_channel_19:00")
        team_channel = interaction.guild.get_channel(team_channel_id)
        if not team_channel:
            await interaction.response.send_message("⚠️ Team List არხი ვერ მოიძებნა.", ephemeral=True)
            return

        entries = record.get("registered_messages_19:00", [])
        messages = [entry["content"] for entry in entries]

        def to_fancy_number(n):
            num_map = {'0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵'}
            return ''.join(num_map[d] for d in f"{n:02}")

        lines = [
            f"> {to_fancy_number(i)}. {messages[25 - i]}" if 25 - i < len(messages)
            else f"> {to_fancy_number(i)}."
            for i in range(25, 0, -1)
        ]

        lines.reverse()

        message = (
            "> \n"
            ">                  __**TEAM LIST**__\n"
            ">                        **19:00**\n"
            + "\n".join(lines)
        )

        await team_channel.send(message)
        await interaction.response.send_message("✅ Team List 19:00 წარმატებით შეიქმნა!", ephemeral=True)

    except Exception as e:
        print(f"Error in createteamlist_19_00: {e}")
        await interaction.response.send_message("⚠️ ქომანდის შესრულებისას მოხდა შეცდომა.", ephemeral=True)


@bot.tree.command(name="clearlist_19_00", description="წაშალე Team List 19:00")
@app_commands.checks.has_permissions(administrator=True)
async def clearlist(interaction: discord.Interaction):

    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    try:
        guild_id = interaction.guild.id
        record = channel_collection.find_one({"guild_id": guild_id})

        if not record or "registered_messages_19:00" not in record:
            await interaction.response.send_message("⚠️ ჯერ არავინ არ არის დარეგისტრირებული 19:00-ზე.")
            return

        team_channel_id = record.get("teamlist_channel_19:00")
        team_channel = interaction.guild.get_channel(team_channel_id)
        if not team_channel:
            await interaction.response.send_message("⚠️ Team List არხი ვერ მოიძებნა.")
            return

        channel_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"registered_messages_19:00": []}}
        )

        await interaction.response.send_message("✅ Team List 19:00 წარმატებით წაიშალა!", ephemeral=True)

    except Exception as e:
        print(f"Error during clearing: {e}")
        await interaction.response.send_message(f"⚠️ შეცდომა მოხდა: {e}", ephemeral=True)


# 22:00 SETUP
@bot.tree.command(name="regchannel_22_00", description="დაარეგისტრირე არხი 22:00 როლით")
@app_commands.describe(channel="არხის ID", role_22_00="22:00 როლი", banned_role="Banned როლი", teamlist_channel="Team List არხი")
@app_commands.checks.has_permissions(administrator=True)
async def regchannel_22_00(interaction: discord.Interaction, channel: discord.TextChannel, role_22_00: discord.Role, banned_role: discord.Role, teamlist_channel: discord.TextChannel):

    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
       return
    
    guild_id = interaction.guild.id

    channel_collection.update_one(
        {"guild_id": guild_id},
        {"$set": {
            "channel_id_22_00": channel.id,
            "role_22_00": role_22_00.id,
            "banned_role": banned_role.id,
            "teamlist_channel_22:00": teamlist_channel.id
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
@app_commands.checks.has_permissions(administrator=True)
async def reg_22_00(interaction: discord.Interaction):

    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
       return
    
    try:
        await interaction.response.defer()  

        guild_id = interaction.guild.id
        record = channel_collection.find_one({"guild_id": guild_id})

        if record and "channel_id_22_00" in record:
            channel = interaction.guild.get_channel(record["channel_id_22_00"])
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

@bot.tree.command(name="createteamlist_22_00", description="შექმნის Team List 22:00")
@app_commands.checks.has_permissions(administrator=True)
async def createteamlist(interaction: discord.Interaction):
    try:
        # await interaction.response.defer(ephemeral=True) - ამოიღეთ defer, რადგან ეს შეიძლება გამოიწვიოს შეცდომა
        member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
        if not member:
            return

        guild_id = interaction.guild.id
        record = channel_collection.find_one({"guild_id": guild_id})

        if not record or "registered_messages_22:00" not in record:
            await interaction.response.send_message("⚠️ ჯერ არავინ არ არის დარეგისტრირებული 22:00-ზე.", ephemeral=True)
            return

        team_channel_id = record.get("teamlist_channel_22:00")
        team_channel = interaction.guild.get_channel(team_channel_id)
        if not team_channel:
            await interaction.response.send_message("⚠️ Team List არხი ვერ მოიძებნა.", ephemeral=True)
            return

        entries = record.get("registered_messages_22:00", [])
        messages = [entry["content"] for entry in entries]

        def to_fancy_number(n):
            num_map = {'0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵'}
            return ''.join(num_map[d] for d in f"{n:02}")

        lines = [
            f"> {to_fancy_number(i)}. {messages[25 - i]}" if 25 - i < len(messages)
            else f"> {to_fancy_number(i)}."
            for i in range(25, 0, -1)
        ]

        lines.reverse()

        message = (
            "> \n"
            ">                  __**TEAM LIST**__\n"
            ">                        **22:00**\n"
            + "\n".join(lines)
        )

        await team_channel.send(message)
        await interaction.response.send_message("✅ Team List წარმატებით შეიქმნა!", ephemeral=True)

    except Exception as e:
        print(f"Error in createteamlist: {e}")
        await interaction.response.send_message("⚠️ ქომანდის შესრულებისას მოხდა შეცდომა.", ephemeral=True)


@bot.tree.command(name="clearlist_22_00", description="წაშალე Team List")
@app_commands.checks.has_permissions(administrator=True)
async def clearlist(interaction: discord.Interaction):

    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    try:
        guild_id = interaction.guild.id
        record = channel_collection.find_one({"guild_id": guild_id})

        if not record or "registered_messages_22:00" not in record:
            await interaction.response.send_message("⚠️ ჯერ არავინ არ არის დარეგისტრირებული 22:00-ზე.")
            return

        team_channel_id = record.get("teamlist_channel_22:00")
        team_channel = interaction.guild.get_channel(team_channel_id)
        if not team_channel:
            await interaction.response.send_message("⚠️ Team List არხი ვერ მოიძებნა.")
            return

        channel_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"registered_messages_22:00": []}}
        )

        await interaction.response.send_message("✅ Team List წარმატებით წაიშალა!", ephemeral=True)

    except Exception as e:
        print(f"Error during clearing: {e}")
        await interaction.response.send_message(f"⚠️ შეცდომა მოხდა: {e}", ephemeral=True)


# 00:30 SETUP
@bot.tree.command(name="regchannel_00_30", description="დაარეგისტრირე არხი 00:30 როლით")
@app_commands.describe(channel="არხის ID", role_00_30="00:30 როლი", banned_role="Banned როლი", teamlist_channel="Team List არხი")
@app_commands.checks.has_permissions(administrator=True)
async def regchannel_00_30(interaction: discord.Interaction, channel: discord.TextChannel, role_00_30: discord.Role, banned_role: discord.Role, teamlist_channel: discord.TextChannel):
    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    guild_id = interaction.guild.id

    channel_collection.update_one(
        {"guild_id": guild_id},
        {"$set": {
            "channel_id_00_30": channel.id,
            "role_00_30": role_00_30.id,
            "banned_role": banned_role.id,
            "teamlist_channel_00:30": teamlist_channel.id
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

@bot.tree.command(name="reg_00_30", description="გამოაგზავნე რეგისტრაციის შეტყობინება")
@app_commands.checks.has_permissions(administrator=True)
async def reg_00_30(interaction: discord.Interaction):
    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    try:
        await interaction.response.defer()

        guild_id = interaction.guild.id
        record = channel_collection.find_one({"guild_id": guild_id})

        if record and "channel_id_00_30" in record:
            channel = interaction.guild.get_channel(record["channel_id_00_30"])
            if channel:
                message = (
                    ">>> #  __**Registration is Open**__\n\n"
                    "🇬🇪 **00:30**﹒:flag_eu: 🇩🇿 **21:30**\n"
                    "__`𝗔𝗱𝘃𝗮𝗻𝗰𝗲𝗱 𝗿𝗼𝗼𝗺 { 𝟯𝘅 𝗹𝗼𝗼𝗧.}`__\n"
                    "||@everyone @here ||"
                )
                await channel.send(message)
                await interaction.followup.send("✅ რეგისტრაციის შეტყობინება წარმატებით გაიგზავნა!")
            else:
                await interaction.followup.send("⚠️ არხი ვერ მოიძებნა.")
        else:
            await interaction.followup.send("⚠️ ჯერ არხი არ არის რეგისტრირებული. გამოიყენე /regchannel_00_30.")

    except Exception as e:
        print(f"Error sending response: {e}")

@bot.tree.command(name="createteamlist_00_30", description="შექმნის Team List 00:30")
@app_commands.checks.has_permissions(administrator=True)
async def createteamlist_00_30(interaction: discord.Interaction):
    try:
        member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
        if not member:
            return

        guild_id = interaction.guild.id
        record = channel_collection.find_one({"guild_id": guild_id})

        if not record or "registered_messages_00:30" not in record:
            await interaction.response.send_message("⚠️ ჯერ არავინ არ არის დარეგისტრირებული 00:30-ზე.", ephemeral=True)
            return

        team_channel_id = record.get("teamlist_channel_00:30")
        team_channel = interaction.guild.get_channel(team_channel_id)
        if not team_channel:
            await interaction.response.send_message("⚠️ Team List არხი ვერ მოიძებნა.", ephemeral=True)
            return

        entries = record.get("registered_messages_00:30", [])
        messages = [entry["content"] for entry in entries]

        def to_fancy_number(n):
            num_map = {'0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵'}
            return ''.join(num_map[d] for d in f"{n:02}")

        lines = [
            f"> {to_fancy_number(i)}. {messages[25 - i]}" if 25 - i < len(messages)
            else f"> {to_fancy_number(i)}."
            for i in range(25, 0, -1)
        ]

        lines.reverse()

        message = (
            "> \n"
            ">                  __**TEAM LIST**__\n"
            ">                        **00:30**\n"
            + "\n".join(lines)
        )

        await team_channel.send(message)
        await interaction.response.send_message("✅ Team List 00:30 წარმატებით შეიქმნა!", ephemeral=True)

    except Exception as e:
        print(f"Error in createteamlist_00_30: {e}")
        await interaction.response.send_message("⚠️ ქომანდის შესრულებისას მოხდა შეცდომა.", ephemeral=True)

@bot.tree.command(name="clearlist_00_30", description="წაშალე Team List 00:30")
@app_commands.checks.has_permissions(administrator=True)
async def clearlist_00_30(interaction: discord.Interaction):
    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    try:
        guild_id = interaction.guild.id
        record = channel_collection.find_one({"guild_id": guild_id})

        if not record or "registered_messages_00:30" not in record:
            await interaction.response.send_message("⚠️ ჯერ არავინ არ არის დარეგისტრირებული 00:30-ზე.")
            return

        team_channel_id = record.get("teamlist_channel_00:30")
        team_channel = interaction.guild.get_channel(team_channel_id)
        if not team_channel:
            await interaction.response.send_message("⚠️ Team List არხი ვერ მოიძებნა.")
            return

        channel_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"registered_messages_00:30": []}}
        )

        await interaction.response.send_message("✅ Team List წარმატებით წაიშალა!", ephemeral=True)

    except Exception as e:
        print(f"Error during clearing: {e}")
        await interaction.response.send_message(f"⚠️ შეცდომა მოხდა: {e}", ephemeral=True)


MAIN_SERVER_ID = 1005186618031869952
ROLE_ID = 1368589143546003587
LOG_CHANNEL_ID = 1365381000619622460

@bot.tree.command(name="giveaccess", description="⚔️ მიანიჭეთ წვდომა მებრძოლს (მხოლოდ მფლობელისთვის)")
@app_commands.describe(
    user="მომხმარებელი, რომელსაც უნდა მიეცეს წვდომა",
    duration="დრო (მაგ. 1d, 5h, 30m)",
    server_id="სერვერის ID (ინფორმაციული, წვდომა გაცემულია მთავარ სერვერზე)"
)
async def giveaccess(interaction: discord.Interaction, user: discord.User, duration: str, server_id: str):
    await bot.wait_until_ready()

    if interaction.user.id != 475160980280705024:
        await send_embed_notification(interaction, "❌ წვდომა უარყოფილია", "🛑 მხოლოდ **Commander** (ბოტის მფლობელი) შეიძლება გასცეს წვდომა!")
        return

    if not server_id.isdigit():
        await send_embed_notification(interaction, "📛 არასწორი სერვერის ID", "📦 Server ID უნდა იყოს მხოლოდ ციფრებით შედგენილი.")
        return

    # მთავარი სერვერზე იმუშავებს ბოტი
    main_guild = bot.get_guild(MAIN_SERVER_ID)
    if not main_guild:
        await send_embed_notification(interaction, "❌ მთავარი სერვერი ვერ მოიძებნა", "დარწმუნდით, რომ ბოტი იმყოფება მთავარ სერვერზე.")
        return

    try:
        time_unit = duration[-1].lower()
        time_value = int(duration[:-1])

        if time_unit == 'd':
            delta = timedelta(days=time_value)
        elif time_unit == 'h':
            delta = timedelta(hours=time_value)
        elif time_unit == 'm':
            delta = timedelta(minutes=time_value)
        else:
            await send_embed_notification(interaction, "📛 უცნობი ერთეული", "🧭 გამოიყენე მხოლოდ: d (დღე), h (საათი), m (წუთი)")
            return

        expiry_time = datetime.utcnow() + delta

        try:
            target_member = await main_guild.fetch_member(user.id)
        except discord.NotFound:
            await send_embed_notification(interaction, "🎯 მოთამაშე არ მოიძებნა", f"{user.mention} არ არის მთავარ სერვერზე.")
            return

        access_role = main_guild.get_role(ROLE_ID)
        if not access_role:
            await send_embed_notification(interaction, "🎖 როლი დაკარგულია", "მთავარ სერვერზე წვდომის როლი ვერ მოიძებნა.")
            return

        await target_member.add_roles(access_role)

        access_entry = {
            "user_id": target_member.id,
            "guild_id": int(server_id),  # აქ ინახება რომელ სერვერზე მიენიჭა წვდომა
            "role_id": ROLE_ID,
            "log_channel_id": LOG_CHANNEL_ID,
            "assigned_by": interaction.user.id,
            "duration": duration,
            "assigned_at": datetime.utcnow(),
            "expiry_time": expiry_time,
            "is_active": True
        }
        access_entries.insert_one(access_entry)

        log_embed = discord.Embed(
            title="🎖 წვდომა გაცემულია (Pixelas Pracks)",
            description=f"🛡 **Access Granted to the Squad Member**\nსერვერის ID: `{server_id}`",
            color=discord.Color.gold()
        )
        log_embed.add_field(name="🎮 მოთამაშე", value=f"{target_member.mention} ({target_member.display_name})", inline=False)
        log_embed.add_field(name="⏳ წვდომის დრო", value=f"{duration}", inline=True)
        log_embed.add_field(name="💣 ვადის ამოწურვა", value=f"<t:{int(expiry_time.timestamp())}:F>", inline=True)
        log_embed.add_field(name="👑 გაცემულია მიერ", value=f"<@{interaction.user.id}> *(Commander)*", inline=False)
        log_embed.set_thumbnail(url=target_member.display_avatar.url)
        log_embed.set_footer(text=f"🎯 Player ID: {target_member.id} | 🗓 Deployment Time")

        log_channel = main_guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(embed=log_embed)

        await send_embed_notification(
            interaction,
            "✅ წვდომა გაცემულია",
            f"🎖 {target_member.mention}-ს მიენიჭა {access_role.name} როლი {duration}-ით.\n"
            f"💥 მოქმედება დასრულდება: <t:{int(expiry_time.timestamp())}:R>"
        )

    except discord.Forbidden:
        await send_embed_notification(interaction, "🚫 წვდომა შეზღუდულია", "🤖 ბოტს არ აქვს საკმარისი უფლებები როლის დასამატებლად")
    except Exception as e:
        await send_embed_notification(interaction, "💥 შეცდომა", f"⚙️ ტექნიკური შეცდომა: `{e}`")
        



@bot.tree.command(name="unlist", description="ამოიღებს მითითებულ ID-ს Team List-დან და წევრს ჩამოართმევს შესაბამის როლს")
@app_commands.describe(message_id="შეტყობინების ID")
@app_commands.checks.has_permissions(administrator=True)
async def unlist(interaction: discord.Interaction, message_id: str):
    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    try:
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        record = db["registered_channels"].find_one({"guild_id": guild_id})

        if not record:
            await interaction.followup.send("⚠️ არხის ჩანაწერი ვერ მოიძებნა.", ephemeral=True)
            return

        registered_messages_keys = {
            "registered_messages_19:00": "role_19_00",
            "registered_messages_22:00": "role_22_00",
            "registered_messages_00:30": "role_00_30"
        }

        try:
            message_id_long = int(message_id)
        except ValueError:
            await interaction.followup.send("❌ გთხოვთ მიუთითოთ სწორი შეტყობინების ID (რიცხვი).", ephemeral=True)
            return

        for time_key, role_key in registered_messages_keys.items():
            if time_key not in record:
                continue

            registered_messages = record[time_key]
            removed_message = next((msg for msg in registered_messages if msg["message_id"] == message_id_long), None)

            if removed_message:
                # ამოვშალოთ სიიდან
                new_list = [msg for msg in registered_messages if msg["message_id"] != message_id_long]
                db["registered_channels"].update_one(
                    {"guild_id": guild_id},
                    {"$set": {time_key: new_list}}
                )

                # როლის წართმევის ლოგიკა
                user_id = removed_message.get("user_id")
                if not user_id:
                    await interaction.followup.send(
                        f"✅ შეტყობინება ID {message_id} ამოღებულია Team List {time_key}-დან.\n⚠️ მაგრამ user_id ვერ მოიძებნა შეტყობინებაში.",
                        ephemeral=True
                    )
                    return

                try:
                    member_to_update = await interaction.guild.fetch_member(user_id)
                except discord.NotFound:
                    await interaction.followup.send(
                        f"✅ შეტყობინება ID {message_id} ამოღებულია Team List {time_key}-დან.\n⚠️ თუმცა მომხმარებელი არ მოიძებნა სერვერზე.",
                        ephemeral=True
                    )
                    return

                role_id = record.get(role_key)
                if not role_id:
                    await interaction.followup.send(
                        f"✅ შეტყობინება ID {message_id} ამოღებულია Team List {time_key}-დან.\n⚠️ მაგრამ შესაბამისი როლი ბაზაში ვერ მოიძებნა ({role_key}).",
                        ephemeral=True
                    )
                    return

                role = interaction.guild.get_role(role_id)
                if not role:
                    await interaction.followup.send(
                        f"✅ შეტყობინება ID {message_id} ამოღებულია Team List {time_key}-დან.\n⚠️ მითითებული როლი ({role_id}) არ მოიძებნა სერვერზე.",
                        ephemeral=True
                    )
                    return

                if role in member_to_update.roles:
                    await member_to_update.remove_roles(role, reason="/unlist ბრძანებით")
                    await interaction.followup.send(
                        f"✅ შეტყობინება ID {message_id} წარმატებით ამოღებულია Team List {time_key}-დან და როლი `{role.name}` ჩამოერთვა.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"✅ შეტყობინება ID {message_id} ამოღებულია Team List {time_key}-დან.\nℹ️ წევრს არ ჰქონდა `{role.name}` როლი.",
                        ephemeral=True
                    )
                return

        # თუ ვერცერთ სიაში ვერ მოიძებნა
        await interaction.followup.send("⚠️ მითითებული ID ვერ მოიძებნა Team List-ში.", ephemeral=True)

    except Exception as e:
        print(f"🔴 შეცდომა /unlist: {e}")
        await interaction.followup.send(f"⚠️ მოხდა შეცდომა: {e}", ephemeral=True)
        

def calculate_points(place, eliminations):
    place_points = {
        1: 15,
        2: 12,
        3: 10,
        4: 8,
        5: 6,
        6: 4,
        7: 2,
        8: 1,
        9: 1,
        10: 1,
        11: 1,
        12: 1
    }

    # თუ ადგილი 13-ზე მეტია, არ დაამატოს ადგილის ქულა, მაგრამ დაამატოს მკვლელობები
    return place_points.get(place, 0) + eliminations


# !createresult - რამდენიმე გუნდის მონაცემების შესატანად
@bot.command()
async def createresult(ctx, *args):
    member = await check_user_permissions_for_ctx(ctx, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    try:
        if len(args) % 3 != 0:
            await ctx.send("❌ გთხოვთ, მიუთითოთ თითოეული გუნდის მონაცემები (TeamName, Place, Kills).")
            return

        for i in range(0, len(args), 3):
            team_name = args[i]
            place = int(args[i + 1])
            eliminations = int(args[i + 2])
            points = calculate_points(place, eliminations)

            guild_id = ctx.guild.id  # თითოეული სერვერის guild_id
            existing = teams_collection.find_one({"guild_id": guild_id, "team_name": team_name})

            if existing:
                # უკვე არსებობს — ვაკეთებთ მხოლოდ ქულების და მკვლელობების განახლებას
                new_eliminations = existing['eliminations'] + eliminations
                new_points = existing['points'] + points

                teams_collection.update_one(
                    {"guild_id": guild_id, "team_name": team_name},
                    {"$set": {
                        "eliminations": new_eliminations,
                        "points": new_points
                    }}
                )
                await ctx.send(f"🔁 განახლებულია: {team_name} – {new_eliminations} მკვლელობა – {new_points} ქულა")
            else:
                # ახალი გუნდი — ვამატებთ
                teams_collection.insert_one({
                    "guild_id": guild_id,  # სერვერის ID
                    "team_name": team_name,
                    "eliminations": eliminations,
                    "points": points
                })
                await ctx.send(f"✅ შედეგი შენახულია: {team_name} – {eliminations} მკვლელობა – {points} ქულა")

    except Exception as e:
        await ctx.send(f"❌ შეცდომა: {e}")
        


def get_centered_y(draw, text, font, center_y):
    bbox = draw.textbbox((0, 0), text, font=font)
    text_height = bbox[3] - bbox[1]
    return center_y - text_height // 2

@bot.command()
async def getresult(ctx):
    try:
        guild_id = ctx.guild.id
        teams = list(teams_collection.find({"guild_id": guild_id}))

        if not teams:
            await ctx.send("❌ მონაცემები არ მოიძებნა ამ სერვერზე.")
            return

        teams = sorted(teams, key=lambda x: x.get("points", 0), reverse=True)[:12]

        img_url = "https://i.imgur.com/ZnCFtPG.png"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(img_url, headers=headers)

        if response.status_code != 200:
            await ctx.send("❌ ვერ ჩაიტვირთა ფონური სურათი.")
            return

        base_image = Image.open(io.BytesIO(response.content)).convert("RGBA")
        draw = ImageDraw.Draw(base_image)

        font_path = "fonts/BebasNeue-Regular.ttf"
        font_default = ImageFont.truetype(font_path, size=30)

        def adjust_font_size(text, font_path, max_width, initial_size):
            font_size = initial_size
            font = ImageFont.truetype(font_path, font_size)
            while font.getlength(text) > max_width and font_size > 10:
                font_size -= 1
                font = ImageFont.truetype(font_path, font_size)
            return font

        def get_centered_y(draw, text, font, center_y):
            bbox = draw.textbbox((0, 0), text, font=font)
            text_height = bbox[3] - bbox[1]
            return center_y - text_height // 2

        start_y = 290
        row_height = 51

        max_teamname_width = 570
        center_team_x = 250
        kills_x = 775
        total_x = 883

        for index, team in enumerate(teams):
            center_y = start_y + index * row_height

            team_name = str(team.get("team_name", "Unknown"))
            kills = str(team.get("eliminations", 0))
            total = str(team.get("points", 0))

            font_team = adjust_font_size(team_name, font_path, max_teamname_width, 30)
            team_text_width = font_team.getlength(team_name)
            team_x = center_team_x - (team_text_width / 2)
            team_y = get_centered_y(draw, team_name, font_team, center_y)
            draw.text((team_x, team_y), team_name, font=font_team, fill="white")

            kills_y = get_centered_y(draw, kills, font_default, center_y)
            draw.text((kills_x, kills_y), kills, font=font_default, fill="black")

            total_y = get_centered_y(draw, total, font_default, center_y)
            draw.text((total_x, total_y), total, font=font_default, fill="black")

        with io.BytesIO() as image_binary:
            base_image.save(image_binary, "PNG")
            image_binary.seek(0)
            await ctx.send(file=discord.File(fp=image_binary, filename="results.png"))

    except Exception as e:
        print(f"[ERROR] getresult: {e}")
        await ctx.send(f"❌ მოხდა შეცდომა: {e}")


# !resultclear - მონაცემების წაშლა
@bot.command()
async def resultclear(ctx):    
    member = await check_user_permissions_for_ctx(ctx, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    teams_collection.delete_many({})
    await ctx.send("🗑️ ყველა შედეგი წაიშალა.")


@bot.command()
async def leaveserver(ctx, guild_id: int):
    """გამოიყვანს ბოტს სერვერიდან"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ თქვენ არ გაქვთ ამის გაკეთების უფლება.")
        return
    
    guild = bot.get_guild(guild_id)
    if guild:
        await guild.leave()
        await ctx.send(f"✅ ბოტი დატოვა სერვერი: {guild.name}")
    else:
        await ctx.send("❌ სერვერი ვერ მოიძებნა.")


@bot.command()
@commands.has_permissions(manage_roles=True)
async def rolerall(ctx, role: discord.Role):
    member = await check_user_permissions_for_ctx(ctx, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    removed_count = 0

    for member in ctx.guild.members:
        if role in member.roles:
            try:
                await member.remove_roles(role)
                removed_count += 1
            except discord.Forbidden:
                pass  # არ აქვს უფლება
            except discord.HTTPException:
                pass  # შეცდომა Discord-ისგან

    await ctx.send(f"✅ `{role.name}` როლი ჩამოერთვა {removed_count} წევრს.")


@bot.command(name="customreactallow")
@commands.has_permissions(administrator=True)
async def set_custom_allow_emoji(ctx, emoji: str):
    guild_id = ctx.guild.id
    try:
        channel_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"custom_react_emoji_allow": emoji}},
            upsert=True
        )
        await ctx.send(f"✅ დადებითი რეაქცია წარმატებით განახლდა: {emoji}")
    except Exception as e:
        await ctx.send("❌ შეცდომა დადებითი ემოჯის შეცვლისას.")
        print(f"[ERROR] {e}")


@bot.command(name="customreactdeny")
@commands.has_permissions(administrator=True)
async def set_custom_deny_emoji(ctx, emoji: str):
    guild_id = ctx.guild.id
    try:
        channel_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"custom_react_emoji_deny": emoji}},
            upsert=True
        )
        await ctx.send(f"✅ უარყოფითი რეაქცია წარმატებით განახლდა: {emoji}")
    except Exception as e:
        await ctx.send("❌ შეცდომა უარყოფითი ემოჯის შეცვლისას.")
        print(f"[ERROR] {e}")
    


@bot.command(name="help")
async def custom_help(ctx):
    embed = discord.Embed(
        title="📘 **დახმარების მენიუ**",
        description=(
            "შეარჩიე ქომანდები ქვემოთ მოცემული კატეგორიებიდან:\n\n"
            "📝 თუ გჭირდება მეტი ინფორმაცია, მიმართე კონკრეტულ ბრძანებას!"
        ),
        color=discord.Color.blue()
    )

    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1828/1828817.png")
    embed.set_footer(text="Bot by Pixelas Pracks | გამოიყენე ბრძანებები გონივრულად 🤖")

    embed.add_field(
        name="🎯 **შედეგების ქომანდები**",
        value=(
            "🔹 `p!createresult` – შედეგების დამატება\n"
            "🔹 `p!getresult` – შედეგების ნახვა\n"
            "🔹 `p!resultclear` – შედეგების წაშლა"
        ),
        inline=False
    )

    embed.add_field(
        name="🎭 **როლების ქომანდები**",
        value="🔹 `p!rolerall @Role` – როლის ჩამორთმევა ყველასთვის",
        inline=False
    )

    embed.add_field(
        name="🔖 **რეგისტრაციის React**",
        value=(
        "🔹 `p!customreactallow (Emoji)` – დადასტურებების ემოჯის დაყენება\n"
        "🔹 `p!customreactdeny (Emoji)` – უარყოფილის ემოჯის დაყენება\n"
        ),
        inline=False
    )

    embed.add_field(
        name="🧩 **Slash ბრძანებები**",
        value=(
            "**🕐 რეგისტრაციის დაყენება**:\n"
            "🔹 `/regchannel_00_30` – რეგისტრაციის დაყენება 00:30-ზე\n"
            "🔹 `/regchannel_19_00` – რეგისტრაციის დაყენება 19:00-ზე\n"
            "🔹 `/regchannel_22_00` – რეგისტრაციის დაყენება 22:00-ზე\n\n"
            "**⏳ რეგისტრაციის გახსნის ბრძანებები**:\n"
            "🔹 `/reg_00_30` – რეგისტრაციის გახსნა 00:30-ზე\n"
            "🔹 `/reg_19_00` – რეგისტრაციის გახსნა 19:00-ზე\n"
            "🔹 `/reg_22_00` – რეგისტრაციის გახსნა 22:00-ზე\n\n"
            "**🏆 Team List შექმნა**:\n"
            "🔹 `/createteamlist_00_30` – Team List - ის შექმნა 00:30-ზე\n"
            "🔹 `/createteamlist_19_00` – Team List - ის შექმნა 19:00-ზე\n"
            "🔹 `/createteamlist_22_00` – Team List - ის შექმნა 22:00-ზე\n\n"
            "**🧹 Team List გასუფთავება**:\n"
            "🔹 `/clearlist_00_30` – Team List - ის გასუფთავება 00:30-ზე\n"
            "🔹 `/clearlist_19_00` – Team List - ის გასუფთავება 19:00-ზე\n"
            "🔹 `/clearlist_22_00` – Team List - ის გასუფთავება 22:00-ზე\n\n"
            "**🚫 Team List - იდან ამოსმა**:\n"
            "🔹 `/unlist` – Team List - იდან ამოსმა"
        ),
        inline=False
    )

    await ctx.send(embed=embed)


@bot.command(name="invite")
async def invite_prefix_command(ctx):
    invite_url = "https://discord.com/oauth2/authorize?client_id=1367947407517810719"
    
    embed = discord.Embed(
        title="🤖 მიიწვიე ჩვენი ბოტი!",
        description=f"[დააწკაპუნე აქ]({invite_url}) ბოტის მოსაწვევად შენს სერვერზე.",
        color=discord.Color.blurple()
    )
    embed.set_footer(text="მადლობა, რომ იყენებ ჩვენს ბოტს!")

    await ctx.send(embed=embed)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    print(f"Command Error: {error}")
    if not interaction.response.is_done():
        await interaction.response.send_message("⚠️ ქომანდის შესრულებისას მოხდა შეცდომა.", ephemeral=True)
    else:
        await interaction.followup.send("⚠️ ქომანდის შესრულებისას მოხდა შეცდომა.", ephemeral=True)
        

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
