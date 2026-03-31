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
            active = conn.execute("SELECT id FROM sessions WHERE user_id = ? AND status = 'ACTIVE'", (user_id,)).fetchone()
            if active:
                if not self.is_sync(ctx): await ctx.send("Finish your current workout first!")
                return

            exercises = conn.execute("""
                SELECT exercise_name FROM user_splits 
                WHERE user_id = ? AND split_name = ? 
                ORDER BY order_index ASC
            """, (user_id, split_name)).fetchall()

            if not exercises:
                if not self.is_sync(ctx): 
                    await ctx.send(f"No split named `{split_name}` found. Use `!set_split` first!")
                return

            # find the ID of the previous session of the same name
            last_session = conn.execute("""
                SELECT id FROM sessions 
                WHERE user_id = ? AND split_name = ? AND status = 'COMPLETED'
                ORDER BY id DESC LIMIT 1
            """, (user_id, split_name)).fetchone()

            # start the new session
            conn.execute("""
                INSERT INTO sessions (user_id, start_time, split_name, status) 
                VALUES (?, ?, ?, 'ACTIVE')
            """, (user_id, start_time, split_name))

        if not self.is_sync(ctx):
            msg = f"**{split_name.upper()} Started!**\n\n**Targets from last session:**\n"
            
            if last_session:
                last_id = last_session[0]
                with db.get_connection() as conn:
                    for (ex_name,) in exercises:
                        # Fetch all sets for this exercise from the last session
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
        
        # Session Check (Isolated by user)
        session = db.get_active_session(user_id)
        if not session:
            if not self.is_sync(ctx):
                await ctx.send("You don't have an active session! Type `!start <split>` first.")
            return

        session_id = session[0]

        # This handles decimals for weight (kg) and optional @RPE
        pattern = r"([a-zA-Z0-9_]+)\s+(\d+(?:\.\d+)?)\s+(\d+)(?:\s+@(\d+))?"
        match = re.search(pattern, content)
        
        if not match:
            if not self.is_sync(ctx):
                await ctx.send("Format error! Use: `exercise weight reps @rpe` (e.g., `bench 80 5 @8`)")
            return

        raw_name, weight, reps, rpe = match.groups()
        rpe_val = rpe if rpe else "N/A"

        # This checks master list and alias table
        exercise_name = db.resolve_exercise(raw_name)
        
        if not exercise_name:
            if not self.is_sync(ctx):
                await ctx.send(
                    f"Exercise `{raw_name}` is not in the system.\n"
                    f"• To add: `!new_ex {raw_name} <category>`\n"
                    f"• To alias: `!alias {raw_name} <master_name>`"
                )
            return

        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO logs (session_id, user_id, exercise, weight, reps, rpe, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, user_id, exercise_name, float(weight), int(reps), rpe_val, msg_ts))

        if not self.is_sync(ctx):
            clean_name = exercise_name.replace('_', ' ').capitalize()
            await ctx.send(f"**{clean_name}**: {weight}kg x {reps} (RPE: {rpe_val})")

    @commands.command()
    async def status(self, ctx, sleep: int = None, fatigue: int = None):
        session = db.get_active_session()
        if not session:
            if not self.is_sync(ctx):
                await ctx.send("No active session found.")
            return

        with db.get_connection() as conn:
            conn.execute("UPDATE sessions SET sleep_score = ?, fatigue_level = ? WHERE id = ?", 
                         (sleep, fatigue, session[0]))
            
        if not self.is_sync(ctx):
            await ctx.send(f"**Status Updated:** Sleep: {sleep if sleep else 'N/A'}, Fatigue: {fatigue if fatigue else 'N/A'}")

    @commands.command()
    async def history(self, ctx, limit: int = 5):
        if self.is_sync(ctx): return 
        
        user_id = ctx.author.id

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT exercise, weight, reps, timestamp 
                FROM logs 
                WHERE user_id = ? 
                ORDER BY id DESC LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()

        if not rows:
            await ctx.send("You haven't logged any lifts yet.")
            return

        msg = f"**Your Recent Lifts (kg):**\n"
        for row in rows:
            time_part = row[3].split('T')[1][:5] if 'T' in row[3] else "N/A"
            msg += f"`{time_part}` | **{row[0].replace('_', ' ').capitalize()}**: {row[1]}kg x {row[2]}\n"
        await ctx.send(msg)

    @commands.command()
    async def finish(self, ctx):
        user_id = ctx.author.id
        session = db.get_active_session(user_id)
        if not session: return await ctx.send("No active session.")

        session_id, split_name = session
        
        with db.get_connection() as conn:
            current_logs = conn.execute("""
                SELECT exercise, weight, reps 
                FROM logs WHERE session_id = ?
            """, (session_id,)).fetchall()

            # find previous completed session of same split
            prev_session = conn.execute("""
                SELECT id FROM sessions 
                WHERE user_id = ? AND split_name = ? AND status = 'COMPLETED' 
                ORDER BY id DESC LIMIT 1
            """, (user_id, split_name)).fetchone()

            analysis_rows = []
            exercises_done = sorted(list(set([log[0] for log in current_logs])))

            for ex in exercises_done:
                curr_sets = [{'w': l[1], 'r': l[2], 'e': l[1] / (1.0278 - (0.0278 * l[2]))} 
                             for l in current_logs if l[0] == ex]
                
                max_weight = max(s['w'] for s in curr_sets)
                working_sets = [s['e'] for s in curr_sets if s['w'] >= (max_weight * 0.8)]
                curr_rsi = sum(working_sets) / len(working_sets)
                prev_rsi = 0
                if prev_session:
                    prev_logs = conn.execute("""
                        SELECT weight, reps FROM logs 
                        WHERE session_id = ? AND exercise = ?
                    """, (prev_session[0], ex)).fetchall()
                    
                    if prev_logs:
                        p_sets = [{'w': l[0], 'r': l[1], 'e': l[0] / (1.0278 - (0.0278 * l[1]))} 
                                  for l in prev_logs]
                        p_max = max(s['w'] for s in p_sets)
                        p_working = [s['e'] for s in p_sets if s['w'] >= (p_max * 0.8)]
                        prev_rsi = sum(p_working) / len(p_working)

                analysis_rows.append({
                    'name': ex.replace('_', ' ').capitalize(),
                    'change': (curr_rsi - prev_rsi) if prev_rsi > 0 else None
                })

            # Close the session
            conn.execute("UPDATE sessions SET end_time = ?, status = 'COMPLETED' WHERE id = ?", 
                         (ctx.message.created_at.isoformat(), session_id))

        # --- Output Table ---
        msg = f" **{split_name.upper()} Complete**\n"
        msg += "```\nExercise         | Strength Change\n"
        msg += "----------------------------------\n"
        
        for row in analysis_rows:
            name = (row['name'][:15] + '..') if len(row['name']) > 15 else row['name'].ljust(16)
            if row['change'] is None:
                change_str = "Baseline"
            else:
                emoji = "▲" if row['change'] >= 0 else "▼"
                change_str = f"{emoji} {abs(row['change']):.1f} kg"
            
            msg += f"{name} | {change_str}\n"
        
        msg += "```"
        await ctx.send(msg)

    @commands.command()
    async def set_split(self, ctx, *, content: str):
        """Format: !set_split Push1, Bench, OHP, Triceps"""
        parts = [p.strip().lower() for p in content.split(',')]
        if len(parts) < 2:
            await ctx.send("Need a name and at least one exercise. e.g., `!set_split Push, Bench, OHP`")
            return

        split_name = parts[0]
        raw_exercises = parts[1:]
        user_id = ctx.author.id
        
        validated_exercises = []
        errors = []

        # Validate each exercise against the Master List/Aliases
        for ex in raw_exercises:
            resolved = db.resolve_exercise(ex)
            if resolved:
                validated_exercises.append(resolved)
            else:
                errors.append(ex)

        if errors:
            error_list = ", ".join([f"`{e}`" for e in errors])
            await ctx.send(f"**Split not saved.** The following exercises are not recognized: {error_list}\n"
                        f"Please add them with `!new_ex` or `!alias` first.")
            return

        # Save the standardized exercises
        with db.get_connection() as conn:
            conn.execute("DELETE FROM user_splits WHERE user_id = ? AND split_name = ?", (user_id, split_name))
            
            for index, ex_name in enumerate(validated_exercises):
                conn.execute("""
                    INSERT INTO user_splits (user_id, split_name, exercise_name, order_index)
                    VALUES (?, ?, ?, ?)
                """, (user_id, split_name, ex_name, index))
        # this is needed so data is instantly written to db
        conn.close()

        await ctx.send(f"**{split_name.capitalize()}** saved with {len(validated_exercises)} validated exercises.")

    @commands.command()
    async def new_ex(self, ctx, name: str, category: str):
        """Usage: !new_ex bench_press Chest"""
        name = name.lower().strip()
        try:
            with db.get_connection() as conn:
                conn.execute("INSERT INTO exercises (name, category) VALUES (?, ?)", (name, category.capitalize()))
            await ctx.send(f"Master exercise `{name}` added to `{category}`.")
        except:
            await ctx.send(f"Exercise `{name}` already exists.")

    @commands.command()
    async def edit_ex(self, ctx, old_name: str, new_name: str):
        """Usage: !edit_ex old_name new_name"""
        old_name = old_name.lower().strip()
        new_name = new_name.lower().strip()

        try:
            with db.get_connection() as conn:
                res = conn.execute("SELECT id FROM exercises WHERE name = ?", (old_name,)).fetchone()
                if not res:
                    await ctx.send(f"Could not find exercise `{old_name}`.")
                    return

                # Update master list
                conn.execute("UPDATE exercises SET name = ? WHERE name = ?", (new_name, old_name))
                # Update history
                conn.execute("UPDATE logs SET exercise = ? WHERE exercise = ?", (new_name, old_name))
                # Update splits
                conn.execute("UPDATE user_splits SET exercise_name = ? WHERE exercise_name = ?", (new_name, old_name))
                
            await ctx.send(f"Renamed `{old_name}` to `{new_name}` across all records.")
        except Exception as e:
            await ctx.send(f"Error: Could not rename. `{new_name}` might already exist.")

    @commands.command()
    async def alias(self, ctx, shorthand: str, master_name: str):
        """Usage: !alias bp bench_press"""
        shorthand = shorthand.lower().strip()
        master_name = master_name.lower().strip()

        with db.get_connection() as conn:
            ex = conn.execute("SELECT id FROM exercises WHERE name = ?", (master_name,)).fetchone()
            if not ex:
                await ctx.send(f"Master exercise `{master_name}` doesn't exist.")
                return
            conn.execute("INSERT OR REPLACE INTO exercise_aliases (alias, exercise_id) VALUES (?, ?)", 
                         (shorthand, ex[0]))
        await ctx.send(f"Alias mapped: `{shorthand}` ➡️ `{master_name}`")

    @commands.command()
    async def list_ex(self, ctx):
        """Lists all known exercises by category"""
        with db.get_connection() as conn:
            data = conn.execute("SELECT name, category FROM exercises ORDER BY category").fetchall()
        
        if not data:
            await ctx.send("No exercises in database.")
            return

        msg = "**Known Exercises:**\n"
        current_cat = ""
        for name, cat in data:
            if cat != current_cat:
                msg += f"\n**{cat}:**\n"
                current_cat = cat
            msg += f"• `{name}`\n"
        await ctx.send(msg)

    @commands.command()
    async def list_splits(self, ctx):
        """Lists all known splits per user"""
        user_id = ctx.author.id
        with db.get_connection() as conn:
            data = conn.execute("SELECT split_name, exercise_name FROM user_splits WHERE user_id = ?", (user_id,)).fetchall()
        
        if not data:
            await ctx.send("No splits in database.")
            return

        msg = "**Known splits:**\n"
        current_split = ""
        for split_name, exercise_name in data:
            if split_name != current_split:
                msg += f"\n**{split_name}:**\n"
                current_split = split_name
            msg += f"• `{exercise_name}`\n"
        await ctx.send(msg)


async def setup(bot):
    await bot.add_cog(Workout(bot))