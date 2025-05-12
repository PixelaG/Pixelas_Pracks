from bot_instance import bot
from main import bot
from discord import app_commands
from your_mongo_connection import channel_collection
import discord
import asyncio
import re


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
                }}} ,
                upsert=True
            )

        except Exception as e:
            print(f"[ERROR] {e}")

    await bot.process_commands(message)


@bot.tree.command(name="regchannel_22_00", description="დაარეგისტრირე არხი 22:00 როლით")
@app_commands.describe(channel="არხის ID", role_22_00="22:00 როლი", banned_role="Banned როლი", teamlist_channel="Team List არხი")
@app_commands.checks.has_permissions(administrator=True)
async def regchannel_22_00(interaction: discord.Interaction, channel: discord.TextChannel, role_22_00: discord.Role, banned_role: discord.Role, teamlist_channel: discord.TextChannel):
    member = await check_user_permissions(interaction, 1368589143546003587, 1005186618031869952)
    if not member:
        await interaction.response.send_message("⚠️ თქვენ არ გაქვთ საკმარისი უფლებები.", ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    try:
        # MongoDB განახლება
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

        await interaction.response.send_message(
            f"✅ არხი `{channel.name}` და როლები წარმატებით დარეგისტრირდა MongoDB-ში!\n"
            f"📄 Team List Channel: `{teamlist_channel.name}`"
        )

    except Exception as e:
        print(f"[ERROR] Error during registration: {e}")
        await interaction.response.send_message(f"⚠️ რეგისტრაციისას მოხდა შეცდომა: {e}", ephemeral=True)


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

        if record and "channel_id" in record:
            channel = interaction.guild.get_channel(record["channel_id"])
            if channel:
                message = (
                    ">>> #  __**Registration is Open**__\n\n"
                    "🇬🇪 **22:00**﹒:flag_eu: 🇩🇿 **19:00**\n"
                    "__𝗔𝗱𝘃𝗮𝗻𝗰𝗲𝗱 𝗿𝗼𝗼𝗺 { 𝟯𝘅 𝗹𝗼𝗼𝗧.}__\n"
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
