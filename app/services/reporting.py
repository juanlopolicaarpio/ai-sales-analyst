import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import httpx
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

from app.config import settings
from app.db import crud, models
from app.services.analytics import get_sales_data
from app.core.agent import sales_analyst_agent


async def send_daily_report(
    db: AsyncSession,
    store_id: str,
    user_id: str
) -> bool:
    """
    Generate and send a daily sales report to a user.
    
    Args:
        db: Database session
        store_id: Store ID
        user_id: User ID
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get user and store
        user = await crud.get_user(db, user_id)
        store = await crud.get_store(db, store_id)
        
        if not user or not store:
            logger.error(f"User or store not found: {user_id}, {store_id}")
            return False
        
        # Get user preferences
        timezone = user.preferences.timezone if user.preferences else "UTC"
        
        # Get yesterday's sales data
        sales_data = await get_sales_data(db, store_id, "yesterday", timezone)
        
        # Generate report text
        report_text = await sales_analyst_agent.generate_daily_summary(sales_data, store.name)
        
        # Determine preferred notification channel
        notification_channel = user.preferences.notification_channel if user.preferences else "email"
        
        # Send report via the preferred channel
        if notification_channel == "slack" and user.slack_user_id:
            return await send_slack_message(user.slack_user_id, report_text)
        
        elif notification_channel == "whatsapp" and user.whatsapp_number:
            return await send_whatsapp_message(user.whatsapp_number, report_text)
        
        elif notification_channel == "email" and user.email:
            return await send_email_report(
                recipient_email=user.email,
                recipient_name=user.full_name or "Store Owner",
                subject=f"Daily Sales Report for {store.name} - {datetime.now().strftime('%Y-%m-%d')}",
                report_text=report_text
            )
        
        else:
            # Default to email
            return await send_email_report(
                recipient_email=user.email,
                recipient_name=user.full_name or "Store Owner",
                subject=f"Daily Sales Report for {store.name} - {datetime.now().strftime('%Y-%m-%d')}",
                report_text=report_text
            )
            
    except Exception as e:
        logger.error(f"Error sending daily report: {e}")
        return False


async def send_anomaly_alerts(
    db: AsyncSession,
    store_id: str,
    alerts: List[Dict[str, Any]]
) -> Dict[str, int]:
    """
    Send anomaly alerts to all users associated with a store.
    
    Args:
        db: Database session
        store_id: Store ID
        alerts: List of alert messages
    
    Returns:
        dict: Counts of successful deliveries by channel
    """
    if not alerts:
        return {"slack": 0, "whatsapp": 0, "email": 0}
    
    # Get all users associated with the store
    store_users = db.query(models.User).join(
        models.store_user_association,
        models.User.id == models.store_user_association.c.user_id
    ).filter(
        models.store_user_association.c.store_id == store_id,
        models.User.is_active == True
    ).all()
    
    results = {"slack": 0, "whatsapp": 0, "email": 0}
    
    for user in store_users:
        # Check if user wants anomaly alerts
        if (user.preferences and 
            user.preferences.notification_preferences and 
            not user.preferences.notification_preferences.get("anomaly_detection", True)):
            continue
        
        # Determine preferred notification channel
        notification_channel = user.preferences.notification_channel if user.preferences else "email"
        
        # Send all alerts via the preferred channel
        for alert in alerts:
            success = False
            
            if notification_channel == "slack" and user.slack_user_id:
                success = await send_slack_message(user.slack_user_id, alert["message"])
                if success:
                    results["slack"] += 1
            
            elif notification_channel == "whatsapp" and user.whatsapp_number:
                success = await send_whatsapp_message(user.whatsapp_number, alert["message"])
                if success:
                    results["whatsapp"] += 1
            
            elif notification_channel == "email" and user.email:
                success = await send_email_report(
                    recipient_email=user.email,
                    recipient_name=user.full_name or "Store Owner",
                    subject=f"Sales Alert: {alert['title']}",
                    report_text=alert["message"]
                )
                if success:
                    results["email"] += 1
    
    return results


async def send_slack_message(slack_user_id: str, message: str) -> bool:
    """
    Send a message to a user via Slack.
    
    Args:
        slack_user_id: Slack user ID
        message: Message text
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not settings.SLACK_BOT_TOKEN:
        logger.error("Slack bot token not configured")
        return False
    
    try:
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        response = client.chat_postMessage(
            channel=slack_user_id,
            text=message
        )
        return True
    except SlackApiError as e:
        logger.error(f"Error sending Slack message: {e}")
        return False


async def send_whatsapp_message(phone_number: str, message: str) -> bool:
    """
    Send a message to a user via WhatsApp.
    
    Args:
        phone_number: User's WhatsApp phone number
        message: Message text
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_PHONE_NUMBER]):
        logger.error("Twilio credentials not configured")
        return False
    
    try:
        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Ensure phone number is in E.164 format
        if not phone_number.startswith("+"):
            phone_number = f"+{phone_number}"
        
        message = client.messages.create(
            body=message,
            from_=f"whatsapp:{settings.TWILIO_PHONE_NUMBER}",
            to=f"whatsapp:{phone_number}"
        )
        
        return True
    except TwilioRestException as e:
        logger.error(f"Error sending WhatsApp message: {e}")
        return False


async def send_email_report(
    recipient_email: str,
    recipient_name: str,
    subject: str,
    report_text: str
) -> bool:
    """
    Send a report via email.
    
    Args:
        recipient_email: Recipient's email address
        recipient_name: Recipient's name
        subject: Email subject
        report_text: Report text
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not all([settings.EMAIL_HOST, settings.EMAIL_PORT, settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD]):
        logger.error("Email credentials not configured")
        return False
    
    try:
        # Create a multipart message
        msg = MIMEMultipart()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = recipient_email
        msg["Subject"] = subject
        
        # Add body to email
        body = f"""
        Hello {recipient_name},
        
        {report_text}
        
        Best regards,
        Your AI Sales Analyst
        """
        
        msg.attach(MIMEText(body, "plain"))
        
        # Create SMTP session
        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
            server.send_message(msg)
        
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False


async def generate_html_report(
    db: AsyncSession,
    store_id: str,
    time_range: str = "last_7_days",
    timezone: str = "UTC"
) -> str:
    """
    Generate an HTML report for the given time range.
    
    Args:
        db: Database session
        store_id: Store ID
        time_range: Time range for the report
        timezone: User's timezone
    
    Returns:
        str: HTML report
    """
    try:
        # Get store
        store = await crud.get_store(db, store_id)
        if not store:
            return "<h1>Store not found</h1>"
        
        # Get sales data
        sales_data = await get_sales_data(db, store_id, time_range, timezone)
        
        # Create HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Sales Report - {store.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; }}
                h1, h2, h3 {{ color: #2c3e50; }}
                .header {{ margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
                .summary-box {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .summary-box h3 {{ margin-top: 0; }}
                .metrics {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 30px; }}
                .metric {{ flex: 1; min-width: 200px; background-color: #fff; border: 1px solid #ddd; border-radius: 5px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
                .metric h4 {{ margin-top: 0; color: #7f8c8d; }}
                .metric .value {{ font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 5px; }}
                .metric .change {{ font-size: 14px; }}
                .positive {{ color: #27ae60; }}
                .negative {{ color: #e74c3c; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
                th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; }}
                tr:hover {{ background-color: #f5f5f5; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Sales Report - {store.name}</h1>
                <p>Period: {sales_data['time_period']['start_date']} to {sales_data['time_period']['end_date']}</p>
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}</p>
            </div>
            
            <div class="summary-box">
                <h3>Summary</h3>
                <div class="metrics">
                    <div class="metric">
                        <h4>Total Sales</h4>
                        <div class="value">${sales_data['summary']['total_sales']:,.2f}</div>
                        <div class="change {('positive' if sales_data['comparison']['sales_change'] >= 0 else 'negative')}">
                            {sales_data['comparison']['sales_change']*100:+.1f}% vs previous period
                        </div>
                    </div>
                    <div class="metric">
                        <h4>Total Orders</h4>
                        <div class="value">{sales_data['summary']['total_orders']}</div>
                        <div class="change {('positive' if sales_data['comparison']['orders_change'] >= 0 else 'negative')}">
                            {sales_data['comparison']['orders_change']*100:+.1f}% vs previous period
                        </div>
                    </div>
                    <div class="metric">
                        <h4>Average Order Value</h4>
                        <div class="value">${sales_data['summary']['average_order_value']:,.2f}</div>
                        <div class="change {('positive' if sales_data['comparison']['aov_change'] >= 0 else 'negative')}">
                            {sales_data['comparison']['aov_change']*100:+.1f}% vs previous period
                        </div>
                    </div>
                </div>
            </div>
            
            <h2>Top Products</h2>
            <table>
                <tr>
                    <th>Product</th>
                    <th>Revenue</th>
                    <th>Quantity</th>
                </tr>
        """
        
        # Add top products
        for product in sales_data.get("top_products", [])[:10]:
            html += f"""
                <tr>
                    <td>{product['name']}</td>
                    <td>${product['revenue']:,.2f}</td>
                    <td>{product['quantity']}</td>
                </tr>
            """
        
        html += """
            </table>
            
            <h2>Anomalies & Insights</h2>
        """
        
        # Add anomalies
        if sales_data.get("anomalies", []):
            for anomaly in sales_data["anomalies"]:
                html += f"""
                <div class="summary-box">
                    <h3>{anomaly.get('title', 'Anomaly Detected')}</h3>
                    <p>{anomaly.get('description', '')}</p>
                </div>
                """
        else:
            html += """
            <p>No significant anomalies detected during this period.</p>
            """
        
        html += """
            <div class="footer" style="margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px; font-size: 12px;">
                <p>This report was automatically generated by AI Sales Analyst.</p>
            </div>
        </body>
        </html>
        """
        
        return html
    except Exception as e:
        logger.error(f"Error generating HTML report: {e}")
        return f"<h1>Error Generating Report</h1><p>An error occurred: {str(e)}</p>"