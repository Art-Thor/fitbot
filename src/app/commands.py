# src/app/commands.py

from datetime import datetime
import os
from .config import settings
from .models.challenge import Challenge, ActivityType, Result
from .models.database import async_session
from sqlalchemy import select, update, func
from .utils.logging import setup_logger

logger = setup_logger(__name__, level=settings.log_level)

# Map channel names to ActivityType
CHANNEL_ACTIVITY = {
    "calories-challenge": ActivityType.CALORIES,
    "cycling-challenge":  ActivityType.CYCLING,
    "running-challenge":  ActivityType.RUNNING,
    "swimming-challenge": ActivityType.SWIMMING,
    "walking-challenge":  ActivityType.WALKING,
}

def register_commands(app):
    @app.command("/challenge")
    async def handle_challenge_command(ack, command, say):
        try:
            # Always acknowledge first
            await ack()
            
            logger.info(f"Received challenge command: {command}")
            
            # Get command text and normalize it
            text = command.get("text", "").strip()
            if not text:
                await say("❌ Please specify a subcommand. Available commands:\n"
                         "• `/challenge start <start_date> <end_date>` - Start a new challenge\n"
                         "• `/challenge status` - Show current challenge status\n"
                         "• `/challenge stop` - Stop the current challenge\n"
                         "• `/challenge leaderboard` - Show the leaderboard\n"
                         "• `/challenge export` - Export results to CSV\n"
                         "• `/challenge recent @user [limit]` - Show recent submissions")
                return
                
            # Split command and handle hyphenated commands
            if "-" in text:
                parts = text.split("-", 1)
                text = f"{parts[0]} {parts[1]}"
            
            parts = text.split()
            subcommand = parts[0].lower()
            channel = command["channel_id"]
            channel_name = command.get("channel_name", "")
            
            logger.info(f"Processing command: subcommand={subcommand}, channel={channel}, channel_name={channel_name}")
            
            # Check if this is a challenge channel
            activity = None
            for suffix, act in CHANNEL_ACTIVITY.items():
                if channel_name.endswith(f"-{suffix}"):
                    activity = act
                    break
            
            if activity is None:
                await say("❌ This channel is not configured for a challenge. "
                         "Please use this command in a challenge channel (e.g., #running-challenge).")
                return

            if subcommand == "start":
                if len(parts) < 3:
                    await say("❌ Please provide start and end dates.\n"
                             "Example: `/challenge start 2025-05-18T00:00 2025-05-19T00:00`")
                    return
                    
                try:
                    sd = datetime.fromisoformat(parts[1])
                    ed = datetime.fromisoformat(parts[2])
                except (ValueError, IndexError) as e:
                    logger.error(f"Invalid date format: {e}")
                    await say("❌ Dates must be in ISO format: 'YYYY-MM-DDTHH:MM'\n"
                             "Example: `2025-05-18T00:00`")
                    return

                try:
                    async with async_session() as db:
                        # deactivate existing
                        await db.execute(
                            update(Challenge)
                            .where(Challenge.slack_channel_id == channel)
                            .values(is_active=False)
                        )
                        # create new
                        ch = Challenge(
                            slack_channel_id=channel,
                            activity_type=activity,
                            start_date=sd,
                            end_date=ed,
                            is_active=True
                        )
                        db.add(ch)
                        await db.commit()
                        logger.info(f"Created new challenge: {ch.id}")
                    await say(f"✅ {activity.value.title()} challenge started from {sd.date()} to {ed.date()}.")
                except Exception as e:
                    logger.error(f"Failed to create challenge: {e}")
                    await say("❌ Failed to create challenge. Please try again.")
                return

            if subcommand == "stop":
                async with async_session() as db:
                    await db.execute(
                        update(Challenge)
                        .where(Challenge.slack_channel_id == channel)
                        .values(is_active=False)
                    )
                    await db.commit()
                await say("✅ Challenge stopped.")
                return

            if subcommand == "status":
                async with async_session() as db:
                    ch = (await db.execute(
                        select(Challenge)
                        .where(
                            Challenge.slack_channel_id == channel,
                            Challenge.is_active == True
                        )
                    )).first()
                    
                    if not ch:
                        return await say("❌ No active challenge in this channel.")
                        
                    # Count participants
                    participants = (await db.execute(
                        select(func.count(func.distinct(Result.user_id)))
                        .where(Result.challenge_id == ch.id)
                    )).scalar()
                    
                    # Count total submissions
                    submissions = (await db.execute(
                        select(func.count())
                        .where(Result.challenge_id == ch.id)
                    )).scalar()
                    
                    msg = (
                        f" *{ch.activity_type.value.title()} Challenge*\n"
                        f"• Period: {ch.start_date.date()} to {ch.end_date.date()}\n"
                        f"• Participants: {participants}\n"
                        f"• Total submissions: {submissions}"
                    )
                    await say(msg)
                return

            if subcommand == "leaderboard":
                async with async_session() as db:
                    stmt = (
                        select(Result.user_id, func.sum(Result.value).label("total"))
                        .join(Challenge)
                        .where(
                            Challenge.slack_channel_id==channel,
                            Challenge.is_active==True
                        )
                        .group_by(Result.user_id)
                        .order_by(func.sum(Result.value).desc())
                        .limit(10)
                    )
                    rows = (await db.execute(stmt)).all()
                if not rows:
                    return await say("🏆 No submissions yet.")
                msg = "🏆 *Leaderboard*\n"
                for i,(uid,total) in enumerate(rows,1):
                    msg += f"{i}. <@{uid}> — {total:.1f}\n"
                return await say(msg)

            if subcommand == "export":
                async with async_session() as db:
                    # Get all results for active challenge
                    stmt = (
                        select(Result)
                        .join(Challenge)
                        .where(
                            Challenge.slack_channel_id == channel,
                            Challenge.is_active == True
                        )
                        .order_by(Result.date.desc())
                    )
                    results = (await db.execute(stmt)).all()
                    
                    if not results:
                        return await say("❌ No results to export.")
                        
                    # Create CSV
                    import csv
                    import io
                    output = io.StringIO()
                    writer = csv.writer(output)
                    writer.writerow(["User", "Date", "Value", "Unit", "Validated"])
                    
                    for r in results:
                        writer.writerow([
                            f"<@{r.user_id}>",
                            r.date.strftime("%Y-%m-%d"),
                            r.value,
                            r.unit,
                            "Yes" if r.is_validated else "No"
                        ])
                        
                    # Upload to Slack
                    from slack_sdk.web.async_client import AsyncWebClient
                    client = AsyncWebClient(token=os.environ["SLACK_BOT_TOKEN"])
                    
                    await client.files_upload_v2(
                        channel=channel,
                        file=output.getvalue().encode(),
                        filename="challenge_results.csv",
                        title="Challenge Results Export"
                    )
                    
                    await say("✅ Results exported to CSV.")
                return

            if subcommand == "recent":
                if len(parts) < 2:
                    return await say("❌ Please specify a user: `/challenge recent @user [limit]`")
                    
                user = parts[1].strip("<@>")
                limit = int(parts[2]) if len(parts) > 2 else 5
                
                async with async_session() as db:
                    stmt = (
                        select(Result)
                        .join(Challenge)
                        .where(
                            Challenge.slack_channel_id == channel,
                            Challenge.is_active == True,
                            Result.user_id == user
                        )
                        .order_by(Result.date.desc())
                        .limit(limit)
                    )
                    results = (await db.execute(stmt)).all()
                    
                    if not results:
                        return await say(f"❌ No recent submissions found for <@{user}>.")
                        
                    msg = f"📊 *Recent submissions for <@{user}>*\n"
                    for r in results:
                        msg += f"• {r.date.strftime('%Y-%m-%d')}: {r.value} {r.unit}\n"
                    await say(msg)
                return

            await say("❌ Unknown subcommand. Use `start | stop | status | leaderboard | export | recent`.")
        except Exception as e:
            logger.error(f"Error handling challenge command: {e}")
            await say("❌ An error occurred while processing your command. Please try again.")