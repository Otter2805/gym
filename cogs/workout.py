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
    async def start(self, ctx, split_name: str):
        user_id = ctx.author.id
        split_name = split_name.lower()
        start_time = ctx.message.created_at.isoformat()

        with db.get_connection() as conn:
            # 1. Active session check
            active = conn.execute("SELECT id FROM sessions WHERE user_id = ? AND status = 'ACTIVE'", (user_id,)).fetchone()
            if active:
                if not self.is_sync(ctx): await ctx.send("⚠️ Finish your current workout first!")
                return

            # 2. Get exercises for this template
            exercises = conn.execute("""
                SELECT exercise_name FROM user_splits 
                WHERE user_id = ? AND split_name = ? 
                ORDER BY order_index ASC
            """, (user_id, split_name)).fetchall()

            if not exercises:
                if not self.is_sync(ctx): 
                    await ctx.send(f"❓ No split named `{split_name}` found. Use `!set_split` first!")
                return

            # 3. Find the ID of the PREVIOUS session of the same name
            last_session = conn.execute("""
                SELECT id FROM sessions 
                WHERE user_id = ? AND split_name = ? AND status = 'COMPLETED'
                ORDER BY id DESC LIMIT 1
            """, (user_id, split_name)).fetchone()

            # 4. Start the new session
            conn.execute("""
                INSERT INTO sessions (user_id, start_time, split_name, status) 
                VALUES (?, ?, ?, 'ACTIVE')
            """, (user_id, start_time, split_name))

        # --- Data Retrieval & Formatting ---
        if not self.is_sync(ctx):
            msg = f"🚀 **{split_name.upper()} Started!**\n\n**Targets from last session:**\n"
            
            if last_session:
                last_id = last_session[0]
                with db.get_connection() as conn:
                    for (ex_name,) in exercises:
                        # Fetch ALL sets for this exercise from the last session
                        sets = conn.execute("""
                            SELECT weight, reps, rpe FROM logs 
                            WHERE session_id = ? AND exercise = ? 
                            ORDER BY id ASC
                        """, (last_id, ex_name)).fetchall()
                        
                        if sets:
                            # Format sets into a string: "100kg x 5, 100kg x 5, 100kg x 4"
                            set_strings = [f"{s[0]}kg x {s[1]} (@{s[2]})" for s in sets]
                            msg += f"🔹 **{ex_name.capitalize()}**:\n   └ `{', '.join(set_strings)}` \n"
                        else:
                            msg += f"🔹 **{ex_name.capitalize()}**: (No data from last time)\n"
            else:
                msg += "No history for this split yet. Set the baseline today!"
            
            await ctx.send(msg)

    @commands.command()
    async def log(self, ctx, *, content: str):
        user_id = ctx.author.id
        msg_ts = ctx.message.created_at.isoformat()
        
        # 1. Get THIS user's active session
        session = db.get_active_session(user_id)
        
        if not session:
            if not self.is_sync(ctx):
                await ctx.send("❌ You don't have an active session. Type `!start [split]` first.")
            return

        session_id = session[0]

        # 2. Parse the lift
        pattern = r"([a-zA-Z_]+)\s+(\d+(?:\.\d+)?)\s+(\d+)(?:\s+@(\d+))?"
        match = re.search(pattern, content)
        
        if match:
            name, weight, reps, rpe = match.groups()
            rpe = rpe if rpe else "N/A"
            
            with db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO logs (session_id, user_id, exercise, weight, reps, rpe, timestamp) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, user_id, name.lower(), float(weight), int(reps), rpe, msg_ts))
            
            if not self.is_sync(ctx):
                # Quick 1RM calculation for the flex
                one_rm = float(weight) / (1.0278 - (0.0278 * int(reps)))
                await ctx.send(f"✅ **{name.capitalize()}**: {weight}kg x {reps} (@{rpe}). 1RM: {round(one_rm)}kg")
        elif not self.is_sync(ctx):
            await ctx.send("❓ Format: `exercise weight reps @rpe` (e.g., `bench 100 5 @8`)")

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
        user_id = ctx.author.id
        session = db.get_active_session(user_id)
        
        if not session:
            if not self.is_sync(ctx): await ctx.send("❌ No active session found.")
            return

        end_time = ctx.message.created_at.isoformat()
        
        with db.get_connection() as conn:
            # Calculate tonnage for this user's session
            tonnage = conn.execute("SELECT SUM(weight * reps) FROM logs WHERE session_id = ?", (session[0],)).fetchone()[0] or 0
            conn.execute("UPDATE sessions SET end_time = ?, status = 'COMPLETED' WHERE id = ?", (end_time, session[0]))

        if not self.is_sync(ctx):
            await ctx.send(f"🏁 **Session Finished!** Total Volume: {tonnage:.2f}kg.")

    @commands.command()
    async def set_split(self, ctx, *, content: str):
        """Format: !set_split Push, Bench, OHP, Triceps"""
        parts = [p.strip().lower() for p in content.split(',')]
        if len(parts) < 2:
            await ctx.send("❓ Need a name and at least one exercise. e.g., `!set_split Push, Bench, OHP`")
            return

        split_name = parts[0]
        exercises = parts[1:]
        user_id = ctx.author.id

        with db.get_connection() as conn:
            # Clear old version of this split for the user
            conn.execute("DELETE FROM user_splits WHERE user_id = ? AND split_name = ?", (user_id, split_name))
            
            # Insert new exercises
            for index, ex in enumerate(exercises):
                conn.execute("""
                    INSERT INTO user_splits (user_id, split_name, exercise_name, order_index)
                    VALUES (?, ?, ?, ?)
                """, (user_id, split_name, ex, index))

        await ctx.send(f"✅ **{split_name.capitalize()}** split saved with {len(exercises)} exercises.")

async def setup(bot):
    await bot.add_cog(Workout(bot))