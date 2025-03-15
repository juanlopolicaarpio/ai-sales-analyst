from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import json

from app.db.database import get_async_db
from app.core.message_processor import message_processor
from app.utils.helpers import validate_slack_signature

router = APIRouter()


@router.post("/slack/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    x_slack_request_timestamp: str = Header(None),
    x_slack_signature: str = Header(None),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Handle incoming events from Slack.
    
    This endpoint handles various Slack events, including messages, app mentions,
    and verification requests.
    """
    # Get the raw request body
    body = await request.body()
    body_text = body.decode("utf-8")
    
    # Verify the request signature
    if not validate_slack_signature(x_slack_request_timestamp, x_slack_signature, body_text):
        logger.warning("Invalid Slack signature")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Slack signature")
    
    # Parse the request data
    try:
        data = json.loads(body_text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse Slack event JSON: {body_text}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    
    # Handle URL verification challenge
    if data.get("type") == "url_verification":
        logger.info("Received Slack URL verification challenge")
        return {"challenge": data.get("challenge")}
    
    # Process the event
    try:
        event = data.get("event", {})
        event_type = event.get("type")
        
        # Only process message events that aren't from the bot itself
        if event_type == "message" and not event.get("bot_id"):
            user_id = event.get("user")
            channel_id = event.get("channel")
            text = event.get("text", "")
            
            # Don't process empty messages or message edits/deletions
            if not text or event.get("subtype") in ["message_changed", "message_deleted"]:
                return {"status": "ignored"}
            
            # Process the message asynchronously to not block the response
            background_tasks.add_task(
                process_slack_message,
                db,
                user_id,
                channel_id,
                text
            )
        
        # Process app_mention events (when the bot is @mentioned)
        elif event_type == "app_mention":
            user_id = event.get("user")
            channel_id = event.get("channel")
            text = event.get("text", "")
            
            # Remove the bot mention from the text
            # This assumes the bot is mentioned first, which is typical
            text = " ".join(text.split()[1:])
            
            # Process the mention asynchronously
            background_tasks.add_task(
                process_slack_message,
                db,
                user_id,
                channel_id,
                text
            )
    
    except Exception as e:
        logger.error(f"Error processing Slack event: {e}")
        # We don't want to return an error to Slack, as it will retry
        # Instead, log the error and return a 200 response
    
    # Always return a 200 OK to acknowledge the event
    return {"status": "ok"}


async def process_slack_message(db: AsyncSession, user_id: str, channel_id: str, text: str):
    """
    Process a message from Slack.
    
    Args:
        db: Database session
        user_id: Slack user ID
        channel_id: Slack channel ID
        text: Message text
    """
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    from app.config import settings
    
    try:
        # Process the message
        response, _ = await message_processor.process_message(
            db=db,
            message_text=text,
            user_identifier={"slack_id": user_id},
            channel="slack"
        )
        
        # Send the response back to Slack
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        client.chat_postMessage(
            channel=channel_id,
            text=response
        )
    except SlackApiError as e:
        logger.error(f"Error sending Slack response: {e}")
    except Exception as e:
        logger.error(f"Error processing Slack message: {e}")