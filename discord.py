import os
from dotenv import load_dotenv
load_dotenv()
import discord
from discord.ext import commands
from aiohttp import web

GUILD_ID = int(os.getenv("GUILD_ID"))
BOT_TOKEN = os.getenv("BOT_TOKEN")

web_server_started = False
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def handle_verification_request(request):
    data = await request.json()
    discord_handle = data.get("discord_handle")
    token = data.get("token")

    if not discord_handle or not token:
        return web.json_response({"status": "error", "message": "Missing data"}, status=400)

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return web.json_response({"status": "error", "message": "Guild not found"}, status=500)

    member = discord.utils.get(guild.members, name=discord_handle.lower())

    if not member:
        return web.json_response({"status": "error", "message": "User not found in server"}, status=404)

    # Send verification
    try:
        verification_link = f"https://vm.deklenn.dev/verify?token={token}"
        embed = discord.Embed(
            title="MTG Inventory Verification",
            description=f"Click the link below to verify your account:\n\n[Verify Account]({verification_link})",
            color=discord.Color.blurple()
        )
        await member.send(embed=embed)
        print(f"Successfully sent verification DM to {discord_handle}")
        
        return web.json_response({"status": "success", "discord_id": str(member.id)})
    
    except discord.Forbidden:
        print(f"Could not DM {discord_handle}")
        return web.json_response({"status": "error", "message": "User has DMs disabled"}, status=403)

async def start_web_server():
    app = web.Application()
    app.router.add_post('/send_verify_dm', handle_verification_request)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8001) 
    await site.start()
    print("Internal bot server listening on port 8001")

@bot.event
async def on_ready():
    global web_server_started
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

    if not web_server_started:
        bot.loop.create_task(start_web_server())
        web_server_started = True

if __name__ == "__main__":
    bot.run(BOT_TOKEN)