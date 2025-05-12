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
OCR_API_KEY = os.getenv("OCR_API_KEY")



client = MongoClient(mongo_uri)
db = client["Pixelas_Pracks"]
channel_collection = db["registered_channels"]
access_entries = db["access_entries"]
collection = db["teams"]


intents = discord.Intents.default()
intents.members = True  
intents.guilds = True
intents.message_content = True 
intents.messages = True
bot = commands.Bot(command_prefix="p!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"✅ Bot connected as {bot.user}")
    await bot.change_presence(status=discord.Status.invisible)
    
    
    bot.loop.create_task(check_expired_roles())
    
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

    guild_id = message.guild.id
    record = channel_collection.find_one({"guild_id": guild_id})

    if not record:
        print(f"[INFO] No record found for guild_id: {guild_id}")
        return

    # სწორი შეტყობინების ფორმატის regex (დაშვებულია / ან | სეპარატორად)
    pattern = r"^[^/\|\n]+[ /|][^/\|\n]+[ /|]<@!?[0-9]+>$"
    content = message.content.strip()

    if not re.match(pattern, content):
        print(f"[INFO] Message format is incorrect: {content}")
        return

    time_configs = [
        ("channel_id_22_00", "role_22_00", "registered_messages_22:00"),
        ("channel_id_19_00", "role_19_00", "registered_messages_19:00"),
        ("channel_id_00_30", "role_00_30", "registered_messages_00:30")
    ]

    for channel_key, role_key, message_key in time_configs:
        if channel_key in record and message.channel.id == record[channel_key]:
            print(f"[INFO] Message in correct channel: {message.channel.id}")

            try:
                # Check banned role
                banned_role_id = record.get("banned_role")
                if banned_role_id:
                    banned_role = message.guild.get_role(banned_role_id)
                    if banned_role and banned_role in message.author.roles:
                        await message.add_reaction("❌")
                        print(f"[INFO] User has banned role: {banned_role.name}")
                        return

                # Get the role ID from the record
                role_id = record.get(role_key)
                if not role_id:
                    print(f"[INFO] No role ID found for {role_key}")
                    return

                role = message.guild.get_role(role_id)
                if role:
                    await message.author.add_roles(role)
                    await message.add_reaction("✅")
                    print(f"[INFO] Role {role.name} assigned to user: {message.author.name}")
                else:
                    print(f"[INFO] Role with ID {role_id} not found in guild.")

                # Save the message in MongoDB
                channel_collection.update_one(
                    {"guild_id": guild_id},
                    {"$addToSet": {
                        message_key: {
                            "message_id": message.id,
                            "content": message.content
                        }
                    }},
                    upsert=True
                )
                print(f"[INFO] Registered message: {content} in MongoDB")

            except Exception as e:
                print(f"[ERROR - on_message]: {e}")
            break  # Stop further checks if one valid channel is found

    await bot.process_commands(message)


@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild:
        return

    guild_id = message.guild.id
    record = channel_collection.find_one({"guild_id": guild_id})

    if not record:
        return  # აქ აკლდა ეს სტრიქონი, ამიტომ იყო შეცდომა

    # ყველა დროის ვერსია (22:00, 19:00, 00:30)
    for time_key in ["22:00", "19:00", "00:30"]:
        channel_id_key = f"channel_id_{time_key}"
        role_key = f"role_{time_key}"
        registered_messages_key = f"registered_messages_{time_key}"

        if channel_id_key in record and message.channel.id == record[channel_id_key]:
            result = channel_collection.update_one(
                {"guild_id": guild_id},
                {"$pull": {registered_messages_key: {"message_id": message.id}}}
            )

            if result.modified_count > 0:
                print(f"[INFO] Removed deleted message from {registered_messages_key}")
        

async def check_expired_roles():
    """შეამოწმებს და ამოიღებს ვადაგასულ როლებს"""
    while True:
        try:
            now = datetime.utcnow()
            expired_entries = access_entries.find({"expiry_time": {"$lt": now}})
            
            for entry in expired_entries:
                guild = bot.get_guild(entry["guild_id"])
                if not guild:
                    continue
                
                try:
                    member = await guild.fetch_member(entry["user_id"])
                    role = guild.get_role(entry["role_id"])
                    
                    if role and member and role in member.roles:
                        await member.remove_roles(role)
                        
                        log_channel = guild.get_channel(entry["log_channel_id"])
                        if log_channel:
                            expired_embed = discord.Embed(
                                title="⏰ დაკარგა წვდომა ",
                                description=f"{member.mention}-ს აღარ აქვს {role.name} როლი",
                                color=discord.Color.red()
                            )
                            expired_embed.add_field(
                                name="🔚 ვადა გაუვიდა",
                                value=f"<t:{int(entry['expiry_time'].timestamp())}:F>",
                                inline=True
                            )
                            await log_channel.send(embed=expired_embed)
                    
                    access_entries.delete_one({"_id": entry["_id"]})
                
                except discord.NotFound:
                    access_entries.delete_one({"_id": entry["_id"]})
                except Exception as e:
                    print(f"შეცდომა როლის ამოღებისას: {e}")
        
        except Exception as e:
            print(f"შეცდომა check_expired_roles-ში: {e}")
        
        await asyncio.sleep(60)


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
async def createteamlist(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)

        member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
        if not member:
            return

        guild_id = interaction.guild.id
        record = channel_collection.find_one({"guild_id": guild_id})

        if not record or "registered_messages_19:00" not in record:
            await interaction.followup.send("⚠️ ჯერ არავინ არ არის დარეგისტრირებული 19:00-ზე.")
            return

        team_channel_id = record.get("teamlist_channel_19:00")
        team_channel = interaction.guild.get_channel(team_channel_id)
        if not team_channel:
            await interaction.followup.send("⚠️ Team List არხი ვერ მოიძებნა.")
            return

        registered_entries = record.get("registered_messages_19:00", [])
        valid_messages = []

        reg_channel_id = record.get("channel_id_19_00")
        reg_channel = interaction.guild.get_channel(reg_channel_id)

        for entry in registered_entries[:]:  # [:] — უსაფრთხო წაშლა ციკლის დროს
            try:
                msg = await reg_channel.fetch_message(entry["message_id"])
                valid_messages.append(msg.content)
            except discord.NotFound:
                # წაშლილია — ამოიშალოს MongoDB-დანაც
                channel_collection.update_one(
                    {"guild_id": guild_id},
                    {"$pull": {"registered_messages_19:00": {"message_id": entry["message_id"]}}}
                )

        if not valid_messages:
            await interaction.followup.send("⚠️ დარეგისტრირებული შეტყობინებები ვერ მოიძებნა.")
            return

        def to_fancy_number(n):
            num_map = {'0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟯', '8': '𝟴', '9': '𝟵'}
            return ''.join(num_map[d] for d in f"{n:02}")

        lines = [
            f"> {to_fancy_number(i)}. {valid_messages[25 - i]}" if 25 - i < len(valid_messages)
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
        await asyncio.sleep(2)
        await interaction.followup.send("✅ Team List წარმატებით შეიქმნა!", ephemeral=True)

    except Exception as e:
        print(f"Error in createteamlist: {e}")
        if not interaction.response.is_done():
            await interaction.followup.send("⚠️ ქომანდის შესრულებისას მოხდა შეცდომა.", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ ქომანდის შესრულებისას მოხდა შეცდომა.", ephemeral=True)


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
async def createteamlist_22(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    guild_id = interaction.guild.id
    record = channel_collection.find_one({"guild_id": guild_id})

    if not record or "registered_messages_22:00" not in record:
        await interaction.followup.send("⚠️ ჯერ არავინ არ არის დარეგისტრირებული 22:00-ზე.")
        return

    team_channel_id = record.get("teamlist_channel_22:00")
    team_channel = interaction.guild.get_channel(team_channel_id)
    if not team_channel:
        await interaction.followup.send("⚠️ Team List არხი ვერ მოიძებნა.")
        return

    registered_entries = record.get("registered_messages_22:00", [])
    valid_messages = []

    reg_channel = interaction.guild.get_channel(record.get("channel_id_22_00"))

    for entry in registered_entries[:]:
        try:
            msg = await reg_channel.fetch_message(entry["message_id"])
            valid_messages.append(msg.content)
        except discord.NotFound:
            channel_collection.update_one(
                {"guild_id": guild_id},
                {"$pull": {"registered_messages_22:00": {"message_id": entry["message_id"]}}}
            )
        except discord.HTTPException as e:
            print(f"HTTP error occurred: {e}")
        except discord.Forbidden as e:
            print(f"Permission error occurred: {e}")

    if not valid_messages:
        await interaction.followup.send("⚠️ დარეგისტრირებული შეტყობინებები ვერ მოიძებნა.")
        return

    def to_fancy_number(n):
        num_map = {'0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵'}
        return ''.join(num_map.get(d, d) for d in f"{n:02}")

    lines = [
        f"> {to_fancy_number(i)}. {valid_messages[25 - i]}" if 25 - i < len(valid_messages)
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
    await interaction.followup.send("✅ Team List წარმატებით შეიქმნა!", ephemeral=True)


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
    await interaction.response.defer(ephemeral=True)

    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    guild_id = interaction.guild.id
    record = channel_collection.find_one({"guild_id": guild_id})

    if not record or "registered_messages_00:30" not in record:
        await interaction.followup.send("⚠️ ჯერ არავინ არ არის დარეგისტრირებული 00:30-ზე.")
        return

    team_channel_id = record.get("teamlist_channel_00:30")
    team_channel = interaction.guild.get_channel(team_channel_id)
    if not team_channel:
        await interaction.followup.send("⚠️ Team List არხი ვერ მოიძებნა.")
        return

    registered_entries = record.get("registered_messages_00:30", [])
    valid_messages = []

    reg_channel = interaction.guild.get_channel(record.get("channel_id_00_30"))

    for entry in registered_entries[:]:
        try:
            msg = await reg_channel.fetch_message(entry["message_id"])
            valid_messages.append(msg.content)
        except discord.NotFound:
            # წაშლილი შეტყობინების ამოღება ბაზიდან
            channel_collection.update_one(
                {"guild_id": guild_id},
                {"$pull": {"registered_messages_00:30": {"message_id": entry["message_id"]}}}
            )

    if not valid_messages:
        await interaction.followup.send("⚠️ დარეგისტრირებული შეტყობინებები ვერ მოიძებნა.")
        return

    def to_fancy_number(n):
        num_map = {'0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵'}
        return ''.join(num_map[d] for d in f"{n:02}")

    lines = [
        f"> {to_fancy_number(i)}. {valid_messages[25 - i]}" if 25 - i < len(valid_messages)
        else f"> {to_fancy_number(i)}."
        for i in range(25, 0, -1)
    ]

    lines.reverse()

    message = (
        "> \n"
        ">                  __**TEAM LIST**__\n"
        ">                       **00:30**\n"
        + "\n".join(lines)
    )

    await team_channel.send(message)
    await interaction.followup.send("✅ Team List წარმატებით შეიქმნა!", ephemeral=True)

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


@app_commands.describe(user="მომხმარებელი, რომელსაც უნდა მიეცეს წვდომა",duration="დრო (მაგ. 1d, 5h, 30m)")
@bot.tree.command(name="giveaccess", description="⚔️ მიანიჭეთ წვდომა მებრძოლს (მხოლოდ მფლობელისთვის)")
async def giveaccess(interaction: discord.Interaction, user: discord.User, duration: str):
    await bot.wait_until_ready()

    BOT_OWNER_ID = 475160980280705024
    if interaction.user.id != BOT_OWNER_ID:
        await send_embed_notification(
            interaction,
            "❌ წვდომა უარყოფილია",
            "🛑 მხოლოდ **Commander** (ბოტის მფლობელი) შეიძლება გასცეს წვდომა!"
        )
        return

    GUILD_ID = 1005186618031869952
    ROLE_ID = 1368589143546003587
    LOG_CHANNEL_ID = 1365381000619622460

    try:
        time_unit = duration[-1].lower()
        time_value = duration[:-1]

        if not time_value.isdigit():
            await send_embed_notification(
                interaction,
                "📛 არასწორი ფორმატი",
                "📦 გამოიყენე მაგ. `1d`, `5h`, `30m` (დღე/საათი/წუთი)"
            )
            return

        time_value = int(time_value)
        if time_unit == 'd':
            delta = timedelta(days=time_value)
        elif time_unit == 'h':
            delta = timedelta(hours=time_value)
        elif time_unit == 'm':
            delta = timedelta(minutes=time_value)
        else:
            await send_embed_notification(
                interaction,
                "📛 უცნობი ერთეული",
                "🧭 გამოიყენე მხოლოდ: `d` (დღე), `h` (საათი), `m` (წუთი)"
            )
            return

        expiry_time = datetime.utcnow() + delta

        target_guild = bot.get_guild(GUILD_ID)
        if not target_guild:
            await send_embed_notification(interaction, "🌐 სერვერი არ მოიძებნა", "დარწმუნდით, რომ ბოტი დაკავშირებულია სერვერთან")
            return

        try:
            target_member = await target_guild.fetch_member(user.id)
        except discord.NotFound:
            await send_embed_notification(interaction, "🎯 მოთამაშე არ მოიძებნა", f"{user.mention} არ არის ბაზაზე.")
            return

        access_role = target_guild.get_role(ROLE_ID)
        if not access_role:
            await send_embed_notification(interaction, "🎖 როლი დაკარგულია", "დარწმუნდით, რომ წვდომის როლი არსებობს")
            return

        await target_member.add_roles(access_role)

        access_entry = {
            "user_id": target_member.id,
            "guild_id": target_guild.id,
            "role_id": access_role.id,
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
            description="🛡 **Access Granted to the Squad Member**",
            color=discord.Color.gold()
        )
        log_embed.add_field(name="🎮 მოთამაშე", value=f"{target_member.mention} (`{target_member.display_name}`)", inline=False)
        log_embed.add_field(name="⏳ წვდომის დრო", value=f"`{duration}`", inline=True)
        log_embed.add_field(name="💣 ვადის ამოწურვა", value=f"<t:{int(expiry_time.timestamp())}:F>", inline=True)
        log_embed.add_field(name="👑 გაცემულია მიერ", value=f"<@{interaction.user.id}> *(Commander)*", inline=False)
        log_embed.set_thumbnail(url=target_member.display_avatar.url)
        log_embed.set_footer(text=f"🎯 Player ID: {target_member.id} | 🗓 Deployment Time")

        log_channel = target_guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(embed=log_embed)

        await send_embed_notification(
            interaction,
            "✅ წვდომა გაცემულია",
            f"🎖 {target_member.mention}-ს მიენიჭა `{access_role.name}` როლი {duration}-ით.\n"
            f"💥 მოქმედება დასრულდება: <t:{int(expiry_time.timestamp())}:R>"
        )

    except discord.Forbidden:
        await send_embed_notification(interaction, "🚫 წვდომა შეზღუდულია", "🤖 ბოტს არ აქვს საკმარისი უფლებები როლის დასამატებლად")
    except Exception as e:
        await send_embed_notification(interaction, "💥 შეცდომა", f"⚙️ ტექნიკური შეცდომა: `{e}`")


@bot.tree.command(name="unlist", description="ამოიღებს მითითებულ ID-ს Team List-დან")
@app_commands.describe(message_id="შეტყობინების ID")
@app_commands.checks.has_permissions(administrator=True)
async def unlist(interaction: discord.Interaction, message_id: str):
    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    try:
        guild_id = interaction.guild.id
        record = db["registered_channels"].find_one({"guild_id": guild_id})

        if not record:
            await interaction.response.send_message("⚠️ არხის ჩანაწერი ვერ მოიძებნა.", ephemeral=True)
            return

        # Check all possible registered messages lists
        registered_messages_keys = [
            "registered_messages_19:00",
            "registered_messages_22:00",
            "registered_messages_00:30"
        ]

        # Loop through the different time slots
        for time_key in registered_messages_keys:
            if time_key not in record:
                continue  # Skip this time slot if it doesn't exist

            registered_messages = record[time_key]

            try:
                message_id_long = int(message_id)
            except ValueError:
                message_id_long = None

            print(f"Looking for message_id: {message_id_long} in {time_key}")

            # Remove the message if it exists in the list
            new_list = [msg for msg in registered_messages if msg["message_id"] != message_id_long]

            if len(new_list) != len(registered_messages):  # A message was removed
                db["registered_channels"].update_one(
                    {"guild_id": guild_id},
                    {"$set": {time_key: new_list}}
                )
                await interaction.response.send_message(f"✅ შეტყობინება ID {message_id} წარმატებით ამოღებულია Team List {time_key}!", ephemeral=True)
                return  # Exit the loop once the message is found and removed

        # If no message was removed after checking all time slots
        await interaction.response.send_message("⚠️ მითითებული ID ვერ მოიძებნა სიაში.", ephemeral=True)

    except Exception as e:
        print(f"Error during unlisting: {e}")
        await interaction.response.send_message(f"⚠️ შეცდომა მოხდა: {e}", ephemeral=True)

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

            existing = collection.find_one({"team_name": team_name})

            if existing:
                # უკვე არსებობს — ვაკეთებთ მხოლოდ ქულების და მკვლელობების განახლებას
                new_eliminations = existing['eliminations'] + eliminations
                new_points = existing['points'] + points

                collection.update_one(
                    {"team_name": team_name},
                    {"$set": {
                        "eliminations": new_eliminations,
                        "points": new_points
                    }}
                )
                await ctx.send(f"🔁 განახლებულია: {team_name} – {new_eliminations} მკვლელობა – {new_points} ქულა")
            else:
                # ახალი გუნდი — ვამატებთ
                collection.insert_one({
                    "user": ctx.author.name,
                    "team_name": team_name,
                    "eliminations": eliminations,
                    "points": points
                })
                await ctx.send(f"✅ შედეგი შენახულია: {team_name} – {eliminations} მკვლელობა – {points} ქულა")

    except Exception as e:
        await ctx.send(f"❌ შეცდომა: {e}")

# !getresult - ყველა გუნდის შედეგის ჩვენება
@bot.command()
async def getresult(ctx):
    member = await check_user_permissions_for_ctx(ctx, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    pipeline = [
        {
            "$group": {
                "_id": "$team_name",
                "total_points": {"$sum": "$points"},
                "total_eliminations": {"$sum": "$eliminations"}
            }
        },
        {
            "$sort": {"total_points": -1}
        }
    ]

    grouped_results = list(collection.aggregate(pipeline))

    if not grouped_results:
        await ctx.send("📭 შედეგები არ არის.")
        return

    msg = "**📊 საბოლოო შედეგები (ქულების მიხედვით დალაგებული):**\n"

    for idx, r in enumerate(grouped_results, start=1):
        team = r['_id']
        total_points = r['total_points']
        kills = r['total_eliminations']
        msg += f"**{idx} ადგილი** – {team}: {kills} მკვლელობა, {total_points} ქულა\n"

    await ctx.send(msg)

# !resultclear - მონაცემების წაშლა
@bot.command()
async def resultclear(ctx):    
    member = await check_user_permissions_for_ctx(ctx, 1368589143546003587, 1005186618031869952)
    if not member:
        return

    collection.delete_many({})
    await ctx.send("🗑️ ყველა შედეგი წაიშალა.")


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
    


@bot.command(name="help")
async def custom_help(ctx):
    embed = discord.Embed(
        title="📘 დახმარების მენიუ",
        description="შეარჩიე ქომანდები ქვემოთ მოცემული კატეგორიებიდან:",
        color=discord.Color.purple()
    )

    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1828/1828817.png")

    embed.add_field(
        name="🎯 **შედეგების ქომანდები**",
        value=(
            "`!createresult` – შედეგების დამატება\n"
            "`!getresult` – შედეგების ნახვა\n"
            "`!resultclear` – შედეგების წაშლა"
        ),
        inline=False
    )

    embed.add_field(
        name="🎭 **როლების ქომანდები**",
        value="`!rolerall @Role` – როლის ჩამორთმევა ყველასთვის",
        inline=False
    )

    embed.add_field(
        name="🧩 **Slash ბრძანებები**",
        value=(
            "`/regchannel_22_00` – რეგისტრაციის დაყენება\n"
            "`/reg_22_00` – რეგისტრაციის გახსნა\n"
            "`/createteamlist_22_00` – Team List - ის შექმნა\n"
            "`/clearlist` – Team List - ის გასუფთავება\n"
            "`/unlist` – Team List - იდან ამოსმა"
        ),
        inline=False
    )

    embed.set_footer(text="Bot by Pixelas Pracks | გამოიყენე ბრძანებები გონივრულად 🤖")
    
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
