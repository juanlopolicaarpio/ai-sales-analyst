from fastapi import APIRouter, Depends, HTTPException, Request, Form, BackgroundTasks, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.twiml.messaging_response import MessagingResponse
from loguru import logger

from app.db.database import get_async_db
from app.core.message_processor import message_processor
from app.utils.helpers import validate_twilio_signature
from app.config import settings

router = APIRouter()


@router.post("/whatsapp/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    Body: str = Form(None),
    From: str = Form(None),
    To: str = Form(None),
    SmsMessageSid: str = Form(None),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Handle incoming messages from WhatsApp via Twilio.
    
    This endpoint receives WhatsApp messages and processes them.
    """
    # Get the raw request
    form_data = await request.form()
    
    # Validate the request is from Twilio
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    
    if not validate_twilio_signature(signature, url, dict(form_data)):
        logger.warning("Invalid Twilio signature")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Twilio signature")
    
    # Extract the message details
    message_body = Body
    from_number = From
    
    # Clean the phone number (remove "whatsapp:" prefix if present)
    if from_number and from_number.startswith("whatsapp:"):
        from_number = from_number[9:]  # Remove "whatsapp:" prefix
    
    # Skip empty messages
    if not message_body:
        resp = MessagingResponse()
        return str(resp)
    
    # Process the message asynchronously to not block the response
    background_tasks.add_task(
        process_whatsapp_message,
        db,
        from_number,
        message_body
    )
    
    # Return an empty response to Twilio
    resp = MessagingResponse()
    return str(resp)


async def process_whatsapp_message(db: AsyncSession, phone_number: str, message_text: str):
    """
    Process a message from WhatsApp.
    
    Args:
        db: Database session
        phone_number: User's phone number
        message_text: Message text
    """
    from twilio.rest import Client as TwilioClient
    from twilio.base.exceptions import TwilioRestException
    
    try:
        # Process the message
        response, _ = await message_processor.process_message(
            db=db,
            message_text=message_text,
            user_identifier={"whatsapp_number": phone_number},
            channel="whatsapp"
        )
        
        # Send the response back to WhatsApp
        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Ensure phone number is in E.164 format
        if not phone_number.startswith("+"):
            phone_number = f"+{phone_number}"
        
        client.messages.create(
            body=response,
            from_=f"whatsapp:{settings.TWILIO_PHONE_NUMBER}",
            to=f"whatsapp:{phone_number}"
        )
    except TwilioRestException as e:
        logger.error(f"Error sending WhatsApp response: {e}")
    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {e}")