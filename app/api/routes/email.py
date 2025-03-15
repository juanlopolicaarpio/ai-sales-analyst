import json
import base64
import email
from email.message import EmailMessage
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.db.database import get_async_db
from app.core.message_processor import message_processor
from app.config import settings

router = APIRouter()


@router.post("/email/inbound")
async def inbound_email(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Handle incoming emails.
    
    This endpoint processes emails forwarded by services like SendGrid's Inbound Parse
    or AWS SES.
    """
    try:
        # Get the request data
        data = await request.json()
        
        # Extract email data based on the email service being used
        # This example assumes SendGrid's Inbound Parse format
        if "email" in data:
            # SendGrid format
            sender_email = data.get("from")
            subject = data.get("subject", "")
            text_content = data.get("text", "")
            
            # If the message has HTML but no text, try to extract text
            if not text_content and "html" in data:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(data["html"], "html.parser")
                text_content = soup.get_text()
            
        elif "Message" in data:
            # AWS SES format (via SNS)
            message = json.loads(data["Message"])
            mail = message.get("mail", {})
            content = message.get("content", "")
            
            # Extract email details
            sender_email = mail.get("source")
            subject = mail.get("commonHeaders", {}).get("subject", "")
            
            # Decode the content (Base64 encoded)
            if content:
                try:
                    decoded_content = base64.b64decode(content).decode("utf-8")
                    msg = email.message_from_string(decoded_content)
                    
                    # Extract text content
                    text_content = ""
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            text_content = part.get_payload(decode=True).decode("utf-8")
                            break
                except Exception as e:
                    logger.error(f"Error decoding email content: {e}")
                    text_content = ""
            else:
                text_content = ""
                
        else:
            # Unknown format
            logger.error(f"Unknown email format: {data}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported email format")
        
        # Process the email asynchronously to not block the response
        if sender_email and text_content:
            background_tasks.add_task(
                process_email_message,
                db,
                sender_email,
                subject,
                text_content
            )
        
        return {"status": "ok"}
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON in email webhook")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing inbound email: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server error")


async def process_email_message(db: AsyncSession, sender_email: str, subject: str, message_text: str):
    """
    Process an email message.
    
    Args:
        db: Database session
        sender_email: Sender's email address
        subject: Email subject
        message_text: Email content
    """
    try:
        # Process the message
        response, _ = await message_processor.process_message(
            db=db,
            message_text=message_text,
            user_identifier={"email": sender_email},
            channel="email"
        )
        
        # Send the response via email
        await send_email_response(sender_email, subject, response)
    except Exception as e:
        logger.error(f"Error processing email message: {e}")


async def send_email_response(recipient_email: str, original_subject: str, response_text: str):
    """
    Send an email response.
    
    Args:
        recipient_email: Recipient's email address
        original_subject: Original email subject
        response_text: Response text
    """
    if not all([settings.EMAIL_HOST, settings.EMAIL_PORT, settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD]):
        logger.error("Email credentials not configured")
        return
    
    try:
        # Create a multipart message
        msg = MIMEMultipart()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = recipient_email
        
        # Add "Re: " prefix if not already present
        if original_subject.lower().startswith("re:"):
            msg["Subject"] = original_subject
        else:
            msg["Subject"] = f"Re: {original_subject}"
        
        # Add body to email
        msg.attach(MIMEText(response_text, "plain"))
        
        # Create SMTP session
        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
            server.send_message(msg)
        
    except Exception as e:
        logger.error(f"Error sending email response: {e}")