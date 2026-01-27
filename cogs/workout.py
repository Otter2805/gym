import discord
from discord.ext import commands
import re
from datetime import datetime
import database as db

class Workout(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_sync(self, ctx):
        """Helper to check if we should keep the bot quiet."""
        return getattr(ctx, "from_sync", False)

    @commands.command()
    async def start(self, ctx):
        session = db.get_active_session()
        if session:
            if not self.is_sync(ctx):
                await ctx.send("⚠️ Session already active!")
            return
        
        # Use message timestamp for the record
        start_time = ctx.message.created_at.isoformat()
        with db.get_connection() as conn:
            conn.execute("INSERT INTO sessions (start_time, status) VALUES (?, 'ACTIVE')", (start_time,))
        
        if not self.is_sync(ctx):
            await ctx.send("🏋️‍♂️ **Workout Started!**")

    @commands.command()
    async def log(self, ctx, *, content: str):
        session = db.get_active_session()
        msg_ts = ctx.message.created_at.isoformat()
        
        if not session:
            with db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO sessions (start_time, status) VALUES (?, 'ACTIVE')", (msg_ts,))
                session_id = cur.lastrowid
            if not self.is_sync(ctx):
                await ctx.send("🆕 *Started new session automatically.*")
        else:
            session_id = session[0]

        pattern = r"([a-zA-Z_]+)\s+(\d+)\s+(\d+)(?:\s+@(\d+))?"
        match = re.search(pattern, content)
        
        if match:
            name, weight, reps, rpe = match.groups()
            rpe = rpe if rpe else "N/A"
            
            with db.get_connection() as conn:
                conn.execute("INSERT INTO logs (session_id, exercise, weight, reps, rpe, timestamp) "
                             "VALUES (?, ?, ?, ?, ?, ?)",
                             (session_id, name, float(weight), int(reps), rpe, msg_ts))
            
            if not self.is_sync(ctx):
                # Feedback in KG
                one_rm = float(weight) / (1.0278 - (0.0278 * int(reps)))
                await ctx.send(f"✅ **{name.capitalize()}**: {weight}kg x {reps} (@{rpe}). 1RM: {round(one_rm)}kg")
        elif not self.is_sync(ctx):
            await ctx.send("❓ Format: `exercise weight reps @rpe`")

    @commands.command()
    async def status(self, ctx, sleep: int = None, fatigue: int = None):
        session = db.get_active_session()
        if not session:
            if not self.is_sync(ctx):
                await ctx.send("❌ No active session found.")
            return

        with db.get_connection() as conn:
            conn.execute("UPDATE sessions SET sleep_score = ?, fatigue_level = ? WHERE id = ?", 
                         (sleep, fatigue, session[0]))
            
        if not self.is_sync(ctx):
            await ctx.send(f"📝 **Status Updated:** Sleep: {sleep if sleep else 'N/A'}, Fatigue: {fatigue if fatigue else 'N/A'}")

    @commands.command()
    async def history(self, ctx, limit: int = 5):
        if self.is_sync(ctx): return # Never show history during a sync boot

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT exercise, weight, reps, timestamp FROM logs ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()

        if not rows:
            await ctx.send("📭 Database is empty.")
            return

        msg = "**📊 Recent Lifts (kg):**\n"
        for row in rows:
            time_part = row[3].split('T')[1][:5] if 'T' in row[3] else "N/A"
            msg += f"`{time_part}` | **{row[0].capitalize()}**: {row[1]}kg x {row[2]}\n"
        await ctx.send(msg)

    @commands.command()
    async def finish(self, ctx):
        session = db.get_active_session()
        if not session:
            if not self.is_sync(ctx):
                await ctx.send("❌ No active session.")
            return

        end_time = ctx.message.created_at.isoformat()
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT SUM(weight * reps) FROM logs WHERE session_id = ?", (session[0],))
            tonnage = c.fetchone()[0] or 0
            c.execute("UPDATE sessions SET end_time = ?, status = 'COMPLETED' WHERE id = ?", (end_time, session[0]))

        if not self.is_sync(ctx):
            await ctx.send(f"🏁 **Session Closed.**\n📊 **Total Volume:** {tonnage:.2f}kg moved.")

async def setup(bot):
    await bot.add_cog(Workout(bot))