Workout Tracker Discord Bot

This Discord bot is a comprehensive training management system designed to log workouts, track strength progression over time, and manage exercise databases directly through Discord. It uses a structured SQLite backend to ensure data integrity and provides real-time feedback on performance gains.
Main Functionality

The application serves as a digital strength coach. Its primary goal is to help users follow a specific "Split" (a routine of exercises), compare their current performance against their last session, and calculate strength changes using Estimated One Rep Max (e1RM) formulas.
Command Reference
Session Management

    !start <split_name>
    Initiates a workout session. It retrieves the exercises associated with that split and displays your performance from the last time you performed this specific routine to help you set targets.

    !log <exercise> <weight> <reps> [@rpe]
    The primary data entry command. Supports decimals for weight and optional RPE (Rate of Perceived Exertion) tracking.
    Example: !log bench 80.5 5 @8

    !status <sleep_score> <fatigue_level>
    Records subjective recovery data (0-10) for the current session to correlate physical state with performance.

    !finish
    Ends the session and generates a Strength Change Table. It compares your current Relative Strength Index (RSI) against your previous session and shows if you've progressed (▲) or regressed (▼) in kg.

Database & Customization

    !set_split <name>, <ex1>, <ex2>, ...
    Creates a custom workout routine. All exercises must exist in the master list before they can be added to a split.

    !new_ex <name> <category>
    Adds a new master exercise to the global database (e.g., !new_ex squat Legs).

    !alias <shorthand> <master_name>
    Creates a shortcut for an exercise so you don't have to type the full name.
    Example: Mapping bp to bench_press.

    !edit_ex <old_name> <new_name>
    Renames an exercise across the entire database, including your historical logs and saved splits.

Information & History

    !history [limit]
    Shows your most recent lifts with timestamps. Defaults to the last 5 entries.

    !list_ex
    Displays all exercises currently recognized by the system categorized by muscle group.

    !list_splits
    Displays all your saved workout routines and the exercises they contain.

Strength Calculation Logic

The bot calculates progression using the Brzycki Formula for Estimated One Rep Max (e1RM):
e1RM=1.0278−(0.0278×reps)weight​

During the !finish command, the bot calculates the average e1RM of your "working sets" (any set within 80% of your max weight for that session) to provide a "Strength Change" metric.
Future Roadmap: AI Integration

The next evolution of this bot involves moving from data storage to intelligent coaching by adding an AI Insights Layer:

    Automated Plateau Detection: AI will analyze historical trends to identify when an exercise has stalled for 3+ weeks and suggest variations or volume adjustments.

    Predictive Readiness: By analyzing the !status data (sleep/fatigue) alongside lifting velocity, the AI will provide a "Daily Readiness Score" before you start a workout, suggesting whether to push for a PR or take a deload.

    Natural Language Logging: Upgrading the !log command to use LLM parsing, allowing for messy inputs like "I did 3 sets of 10 on bench with 60kg and it felt like a 7 rpe."

    Personalized Programming: AI-generated splits based on the user's weak points identified in the strength change history.
