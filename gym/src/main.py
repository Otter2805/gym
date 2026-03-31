import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import database
from datetime import timezone
from datetime import datetime

database.init_db()

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

class GymBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        await self.load_extension('cogs.workout')
        print("Loaded Cog: Workout")

bot = GymBot()

@bot.event
async def on_ready():
    print(f'{bot.user.name} is online. Starting Sync...')
    last_ts = database.get_last_log_timestamp()
    channel = bot.get_channel(1465795764386267404) 
    
    if last_ts and channel:
        last_dt = datetime.fromisoformat(last_ts).replace(tzinfo=timezone.utc)
        
        print(f"Checking messages after {last_dt}")

        # 2. Fetch messages from Discord since last_dt
        async for message in channel.history(after=last_dt, oldest_first=True):
            if message.author == bot.user:
                continue
            
            ctx = await bot.get_context(message)
            if ctx.valid:
                print(f"Syncing: {message.content}")
                ctx.from_sync = True # This keeps the bot silent during sync
                await bot.invoke(ctx)

    print("--- Sync Complete ---")

bot.run(TOKEN)