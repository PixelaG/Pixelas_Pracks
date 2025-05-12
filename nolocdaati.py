from bot_instance import bot
from discord import app_commands
import discord
import asyncio


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
            "channel_id": channel.id,
            "role_00_30": role_00_30.id,
            "banned_role": banned_role.id,
            "teamlist_channel_00:30": teamlist_channel.id
        }},
        upsert=True
    )

    try:
        await interaction.response.send_message(
            f"✅ არხი {channel.name} და როლები წარმატებით დარეგისტრირდა MongoDB-ში!\n"
            f"📄 Team List Channel: {teamlist_channel.name}"
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

        if record and "channel_id" in record:
            channel = interaction.guild.get_channel(record["channel_id"])
            if channel:
                message = (
                    ">>> #  __**Registration is Open**__\n\n"
                    "🇬🇪 **00:30**﹒:flag_eu: 🇩🇿 **19:00**\n"
                    "__𝗔𝗱𝘃𝗮𝗻𝗰𝗲𝗱 𝗿𝗼𝗼𝗺 { 𝟯𝘅 𝗹𝗼𝗼𝗧.}__\n"
                    "||@everyone @here ||"
                )
                await channel.send(message)
                await interaction.followup.send("✅ რეგისტრაციის შეტყობინება წარმატებით გაიგზავნა!")
            else:
                await interaction.followup.send("⚠️ არხი ვერ მოიძებნა.")
        else:
            await interaction.followup.send("⚠️ ჯერ არხი არ არის რეგისტრირებული. გამოიყენე /regchannel_00:30.")

    except Exception as e:
        print(f"Error sending response: {e}")

@bot.tree.command(name="createteamlist_00_30", description="შექმნის Team List 00:30")
@app_commands.checks.has_permissions(administrator=True)
async def createteamlist_00_30(interaction: discord.Interaction):
    try:
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
        await asyncio.sleep(2)
        await interaction.followup.send("✅ Team List წარმატებით შეიქმნა!", ephemeral=True)

    except Exception as e:
        print(f"Error in createteamlist: {e}")
        if not interaction.response.is_done():
            await interaction.followup.send("⚠️ ქომანდის შესრულებისას მოხდა შეცდომა.", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ ქომანდის შესრულებისას მოხდა შეცდომა.", ephemeral=True)


@bot.tree.command(name="clearlist_00_30", description="წაშალე Team List")
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
