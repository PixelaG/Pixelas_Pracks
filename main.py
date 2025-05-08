import os
import re
import time
import discord
import asyncio
from discord.ext import commands
from discord import app_commands
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
access_entries = db["access_entries"]


intents = discord.Intents.default()
intents.members = True  # აუცილებელია წევრების წვდომისთვის
intents.guilds = True
intents.message_content = True # აუცილებელია ტექსტური შეტყობინებების წასაკითხად
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot connected as {bot.user}")
    await bot.change_presence(status=discord.Status.invisible)
    
    # დაწყება ვადაგასული როლების შემოწმების
    bot.loop.create_task(check_expired_roles())
    
    try:
        # აღადგინე აქტიური როლები ბოტის რესტარტის შემთხვევაში
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

    if record and "channel_id" in record and message.channel.id == record["channel_id"]:
        try:
            banned_role_id = record["banned_role"]
            banned_role = message.guild.get_role(banned_role_id)

            if banned_role in message.author.roles:
                await message.add_reaction("❌")
                return
            
            # ტექსტის ფორმატის შემოწმება (არ დავადოთ რეაქცია ❌)
            pattern = r"^[^\n]+[ /|][^\n]+[ /|]<@!?[0-9]+>$"
            if not re.match(pattern, message.content.strip()):
                return

            # სწორი შეტყობინებაა
            await message.add_reaction("✅")
            role = message.guild.get_role(record["role_22_00"])
            if role:
                await message.author.add_roles(role)

            channel_collection.update_one(
                {"guild_id": guild_id},
                {"$addToSet": {"registered_messages": {
                    "message_id": message.id,
                    "content": message.content
                }}},
                upsert=True
            )

        except Exception as e:
            print(f"[ERROR] {e}")

    await bot.process_commands(message)

@bot.event
async def on_message_edit(before, after):
    if after.author.bot or not after.guild:
        return

    guild_id = after.guild.id
    record = channel_collection.find_one({"guild_id": guild_id})
    if not record or "channel_id" not in record or after.channel.id != record["channel_id"]:
        return

    pattern = r"^[^\n]+[ /|][^\n]+[ /|]<@!?[0-9]+>$"
    if not re.match(pattern, after.content.strip()):
        return

    updated = channel_collection.update_one(
        {"guild_id": guild_id, "registered_messages.message_id": after.id},
        {"$set": {"registered_messages.$.content": after.content}}
    )

    if updated.modified_count:
        print(f"[INFO] Updated message {after.id} with new content.")
        

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
                        
                        # ლოგირება
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
                    
                    # წაშალე ჩანაწერი ბაზიდან
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

# /regchannel ბრძანება
@bot.tree.command(name="regchannel_22_00", description="დაარეგისტრირე არხი 22:00 როლით")
@app_commands.describe(channel="არხის ID", role_22_00="22:00 როლი", banned_role="Banned როლი", teamlist_channel="Team List არხი")
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.checks.has_permissions(administrator=True)
async def reg_22_00(interaction: discord.Interaction):

    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
       return
    
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

@bot.tree.command(name="createteamlist_22_00", description="შექმნის Team List 22:00")
@app_commands.checks.has_permissions(administrator=True)
async def createteamlist(interaction: discord.Interaction):
    try:
        #.defer for awaiting message followup without blocking
        await interaction.response.defer(ephemeral=True)

        # Check user permissions
        member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
        if not member:
            return

        # Database Interaction
        guild_id = interaction.guild.id
        record = channel_collection.find_one({"guild_id": guild_id})

        if not record or "registered_messages" not in record:
            await interaction.followup.send("⚠️ ჯერ არავინ არ არის დარეგისტრირებული.")
            return

        # Find the team channel
        team_channel_id = record.get("teamlist_channel")
        team_channel = interaction.guild.get_channel(team_channel_id)
        if not team_channel:
            await interaction.followup.send("⚠️ Team List არხი ვერ მოიძებნა.")
            return

        # Process registered messages
        entries = record["registered_messages"]
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
            + "\n".join(lines) +
            "\n>\n> || @everyone  ||"
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

@bot.tree.command(name="clearlist", description="წაშალე Team List")
@app_commands.checks.has_permissions(administrator=True)
async def clearlist(interaction: discord.Interaction):

    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
       return
    
    try:
        guild_id = interaction.guild.id
        record = channel_collection.find_one({"guild_id": guild_id})

        if not record or "registered_messages" not in record:
            await interaction.response.send_message("⚠️ ჯერ არავინ არ არის დარეგისტრირებული.")
            return

        team_channel_id = record.get("teamlist_channel")
        team_channel = interaction.guild.get_channel(team_channel_id)
        if not team_channel:
            await interaction.response.send_message("⚠️ Team List არხი ვერ მოიძებნა.")
            return

        # Clear the registered messages
        channel_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"registered_messages": []}}
        )

        await interaction.response.send_message("✅ Team List წარმატებით წაიშალა!", ephemeral=True)

    except Exception as e:
        print(f"Error during clearing: {e}")
        await interaction.response.send_message(f"⚠️ შეცდომა მოხდა: {e}", ephemeral=True)


# /giveaccess command - ONLY FOR BOT OWNER
@app_commands.describe(
    user="მომხმარებელი, რომელსაც უნდა მიეცეს წვდომა",
    duration="დრო (მაგ. 1d, 5h, 30m)"
)
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
        # დროის პარსინგი
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

        # სერვერისა და მომხმარებლის პოვნა
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

        # როლის მინიჭება
        await target_member.add_roles(access_role)

        # MongoDB-ში შენახვა
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

        # EMBED - წვდომის ლოგი PUBG სტილში
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

        # პასუხი მფლობელს
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
        record = channel_collection.find_one({"guild_id": guild_id})

        if not record or "registered_messages" not in record:
            await interaction.response.send_message("⚠️ ჯერ არავინ არ არის დარეგისტრირებული.")
            return

        registered_messages = record["registered_messages"]

        # მოძებნოს შეტყობინება მოცემული ID-ით
        new_list = [msg for msg in registered_messages if msg["message_id"] != message_id]

        if len(new_list) == len(registered_messages):
            await interaction.response.send_message("⚠️ მითითებული ID ვერ მოიძებნა სიაში.", ephemeral=True)
            return

        # განახლება MongoDB-ში
        channel_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"registered_messages": new_list}}
        )

        await interaction.response.send_message(f"✅ შეტყობინება ID {message_id} წარმატებით ამოღებულია სიიდან!", ephemeral=True)

    except Exception as e:
        print(f"Error during unlisting: {e}")
        await interaction.response.send_message(f"⚠️ შეცდომა მოხდა: {e}", ephemeral=True)

@bot.tree.command(name="test", description="Test command")
async def test_command(interaction: discord.Interaction):
    await interaction.response.send_message("Test successful!")


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
