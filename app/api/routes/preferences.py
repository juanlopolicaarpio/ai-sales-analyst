from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_async_db
from app.db import models
from app.api.routes.auth import get_current_active_user
from app.utils.logger import logger

router = APIRouter()

class UserPreferenceBase(BaseModel):
    notification_channel: Optional[str] = "slack"  # slack, whatsapp, email
    daily_report_time: Optional[str] = "17:00"  # 24-hour format
    timezone: Optional[str] = "UTC"
    notification_preferences: Optional[Dict] = {
        "sales_alerts": True,
        "anomaly_detection": True,
        "daily_summary": True
    }

class UserPreferenceResponse(UserPreferenceBase):
    id: str
    user_id: str
    
    class Config:
        orm_mode = True

@router.get("/preferences", response_model=UserPreferenceResponse)
async def get_user_preferences(
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_active_user)
):
    """Get preferences for the current user."""
    result = await db.execute(
        select(models.UserPreference).where(models.UserPreference.user_id == current_user.id)
    )
    preferences = result.scalars().first()
    
    if not preferences:
        # Create default preferences if they don't exist
        preferences = models.UserPreference(
            user_id=current_user.id,
            notification_channel="slack" if current_user.slack_user_id else ("whatsapp" if current_user.whatsapp_number else "email"),
            daily_report_time="17:00",
            timezone="UTC",
            notification_preferences={
                "sales_alerts": True,
                "anomaly_detection": True,
                "daily_summary": True
            }
        )
        db.add(preferences)
        await db.commit()
        await db.refresh(preferences)
    
    return preferences

@router.put("/preferences", response_model=UserPreferenceResponse)
async def update_user_preferences(
    preferences_data: UserPreferenceBase,
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_active_user)
):
    """Update preferences for the current user."""
    result = await db.execute(
        select(models.UserPreference).where(models.UserPreference.user_id == current_user.id)
    )
    preferences = result.scalars().first()
    
    if not preferences:
        # Create preferences if they don't exist
        preferences = models.UserPreference(
            user_id=current_user.id,
            notification_channel=preferences_data.notification_channel,
            daily_report_time=preferences_data.daily_report_time,
            timezone=preferences_data.timezone,
            notification_preferences=preferences_data.notification_preferences
        )
        db.add(preferences)
    else:
        # Update existing preferences
        if preferences_data.notification_channel is not None:
            preferences.notification_channel = preferences_data.notification_channel
        if preferences_data.daily_report_time is not None:
            preferences.daily_report_time = preferences_data.daily_report_time
        if preferences_data.timezone is not None:
            preferences.timezone = preferences_data.timezone
        if preferences_data.notification_preferences is not None:
            preferences.notification_preferences = preferences_data.notification_preferences
    
    await db.commit()
    await db.refresh(preferences)
    
    return preferences

@router.post("/preferences/test-notification", response_model=Dict)
async def test_notification(
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_active_user)
):
    """Send a test notification using the user's preferred channel."""
    from app.core.message_processor import message_processor
    
    result = await db.execute(
        select(models.UserPreference).where(models.UserPreference.user_id == current_user.id)
    )
    preferences = result.scalars().first()
    
    if not preferences:
        raise HTTPException(status_code=404, detail="User preferences not found")
    
    channel = preferences.notification_channel
    
    # Create a test message
    test_message = "This is a test notification from your AI Sales Analyst. If you're receiving this, your notification settings are working correctly!"
    
    success = False
    
    try:
        if channel == "slack" and current_user.slack_user_id:
            from app.services.reporting import send_slack_message
            success = await send_slack_message(current_user.slack_user_id, test_message)
        elif channel == "whatsapp" and current_user.whatsapp_number:
            from app.services.reporting import send_whatsapp_message
            success = await send_whatsapp_message(current_user.whatsapp_number, test_message)
        elif channel == "email" and current_user.email:
            from app.services.reporting import send_email_report
            success = await send_email_report(
                current_user.email,
                current_user.full_name or "Store Owner",
                "Test Notification",
                test_message
            )
        else:
            return {
                "status": "error",
                "message": f"Cannot send test notification through channel '{channel}'. Please update your contact information or change your notification channel."
            }
            
        if success:
            return {
                "status": "success",
                "message": f"Test notification sent successfully via {channel}."
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to send test notification via {channel}. Please check your credentials."
            }
            
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }