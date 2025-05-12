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

from cxrameti import setup as setup_19
from ocdaori import setup as setup_22

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
    await setup_19(bot)
    await setup_22(bot)
    
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

    if record and "channel_id" in record and message.channel.id == record["channel_id"]:
        try:
            banned_role_id = record["banned_role"]
            banned_role = message.guild.get_role(banned_role_id)

            if banned_role in message.author.roles:
                await message.add_reaction("❌")
                return
            
            pattern = r"^[^\n]+[ /|][^\n]+[ /|]<@!?[0-9]+>$"
            if not re.match(pattern, message.content.strip()):
                return

            await message.add_reaction("✅")
            role = message.guild.get_role(record["role_22_00"])
            if role:
                await message.author.add_roles(role)

            channel_collection.update_one(
                {"guild_id": guild_id},
                {"$addToSet": {"registered_messages_22:00": {
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
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
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
