import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import database

# Initialize the DB file on startup
database.init_db()

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

class GymBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        # This loads your workout.py file from the cogs folder
        await self.load_extension('cogs.workout')
        print("Loaded Cog: Workout")

bot = GymBot()

@bot.event
async def on_ready():
    print(f'✅ {bot.user.name} is online. Starting Sync...')
    
    # 1. Get the last time we recorded something
    last_ts = database.get_last_log_timestamp()
    channel = bot.get_channel('sessies')
    
    if last_ts and channel:
        last_dt = datetime.fromisoformat(last_ts)
        # 2. Fetch messages from Discord since last_dt
        async for message in channel.history(after=last_dt, oldest_first=True):
            if message.author == bot.user:
                continue
            
            # 3. Manually invoke the command from the old message
            ctx = await bot.get_context(message)
            if ctx.valid:
                print(f"Syncing missed command: {message.content} from {message.created_at}")
                await bot.invoke(ctx)

    print("--- Sync Complete ---")

bot.run(TOKEN)