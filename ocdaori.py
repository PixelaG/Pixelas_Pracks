import discord
from discord import app_commands
from discord.ext import commands
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["Pixelas_Pracks"]
channel_collection = db["registered_channels"]

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

class TwentyTwoCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="regchannel_22_00", description="დაარეგისტრირე არხი 22:00 როლით")
    @app_commands.describe(channel="არხის ID", role_22_00="22:00 როლი", banned_role="Banned როლი", teamlist_channel="Team List არხი")
    @app_commands.checks.has_permissions(administrator=True)
    async def regchannel_22_00(self, interaction: discord.Interaction, channel: discord.TextChannel, role_22_00: discord.Role, banned_role: discord.Role, teamlist_channel: discord.TextChannel):
        member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
        if not member:
            return
        
        guild_id = interaction.guild.id

        channel_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {
                "channel_id": channel.id,
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

    @app_commands.command(name="reg_22_00", description="გამოაგზავნე რეგისტრაციის შეტყობინება")
    @app_commands.checks.has_permissions(administrator=True)
    async def reg_22_00(self, interaction: discord.Interaction):
        member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
        if not member:
            return
        
        try:
            await interaction.response.defer()  

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

    @app_commands.command(name="createteamlist_22_00", description="შექმნის Team List 22:00")
    @app_commands.checks.has_permissions(administrator=True)
    async def createteamlist_22_00(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)

            member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
            if not member:
                return

            guild_id = interaction.guild.id
            record = channel_collection.find_one({"guild_id": guild_id})

            if not record or "registered_messages_22:00" not in record:
                await interaction.followup.send("⚠️ ჯერ არავინ არ არის დარეგისტრირებული 22:00-ზე.", ephemeral=True)
                return

            team_channel_id = record.get("teamlist_channel_22:00")
            team_channel = interaction.guild.get_channel(team_channel_id)
            if not team_channel:
                await interaction.followup.send("⚠️ Team List არხი ვერ მოიძებნა.", ephemeral=True)
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
            await asyncio.sleep(2)
            await interaction.followup.send("✅ Team List წარმატებით შეიქმნა!", ephemeral=True)

        except Exception as e:
            print(f"Error in createteamlist: {e}")
            if not interaction.response.is_done():
                await interaction.followup.send("⚠️ ქომანდის შესრულებისას მოხდა შეცდომა.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ ქომანდის შესრულებისას მოხდა შეცდომა.", ephemeral=True)

    @app_commands.command(name="clearlist_22_00", description="წაშალე Team List 22:00")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearlist_22_00(self, interaction: discord.Interaction):
        member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
        if not member:
            return

        try:
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

            channel_collection.update_one(
                {"guild_id": guild_id},
                {"$set": {"registered_messages_22:00": []}}
            )

            await interaction.response.send_message("✅ Team List 22:00 წარმატებით წაიშალა!", ephemeral=True)

        except Exception as e:
            print(f"Error during clearing: {e}")
            await interaction.response.send_message(f"⚠️ შეცდომა მოხდა: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(TwentyTwoCommands(bot))
