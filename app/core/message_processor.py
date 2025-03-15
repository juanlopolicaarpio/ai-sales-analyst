import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent import sales_analyst_agent
from app.db import crud
from app.db.models import User, Store
from app.utils.helpers import extract_query_intent
from app.services.analytics import get_sales_data


class MessageProcessor:
    """
    Process incoming messages from different channels and coordinate responses.
    """
    
    @staticmethod
    async def process_message(
        db: AsyncSession,
        message_text: str,
        user_identifier: Dict[str, str],
        channel: str
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Process an incoming message and generate a response.
        
        Args:
            db: Database session
            message_text: The message text
            user_identifier: Dictionary with user identifier (slack_id, whatsapp_number, or email)
            channel: The channel (slack, whatsapp, email)
        
        Returns:
            tuple: (response_text, metadata)
        """
        # Find the user based on the channel and identifier
        user = None
        if channel == "slack" and "slack_id" in user_identifier:
            user = await crud.get_user_by_slack_id(db, user_identifier["slack_id"])
        elif channel == "whatsapp" and "whatsapp_number" in user_identifier:
            user = await crud.get_user_by_whatsapp(db, user_identifier["whatsapp_number"])
        elif channel == "email" and "email" in user_identifier:
            user = await crud.get_user_by_email(db, user_identifier["email"])
        
        if not user:
            logger.warning(f"Unknown user tried to send message via {channel}: {user_identifier}")
            return "I don't recognize you as an authorized user. Please contact your administrator to set up your account.", None
        
        # Log the incoming message
        await crud.create_message(db, {
            "user_id": str(user.id),
            "channel": channel,
            "direction": "incoming",
            "content": message_text,
            "metadata": user_identifier
        })
        
        # Get the user's stores
        stores = await crud.get_stores_by_user(db, str(user.id))
        if not stores:
            return "I couldn't find any connected stores for your account. Please set up at least one store to get started.", None
        
        # For simplicity, use the first store
        store = stores[0]
        
        # Extract intent from the message
        intent = extract_query_intent(message_text)
        
        # Get user context
        user_context = {
            "name": user.full_name or "Store Owner",
            "store_name": store.name,
            "platform": store.platform,
            "timezone": user.preferences.timezone if user.preferences else "UTC"
        }
        
        # Get relevant sales data based on the intent
        sales_data = None
        try:
            if any(keyword in message_text.lower() for keyword in ["sales", "revenue", "orders", "products"]):
                sales_data = await get_sales_data(
                    db, 
                    str(store.id), 
                    intent["time_range"],
                    user_context["timezone"]
                )
        except Exception as e:
            logger.error(f"Error getting sales data: {e}")
            # Continue without sales data
        
        # Use AI agent to generate response
        try:
            response = await sales_analyst_agent.analyze_query(
                query=message_text,
                user_context=user_context,
                sales_data=sales_data
            )
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            response = "I'm sorry, I encountered an error while processing your request. Please try again later."
        
        # Log the outgoing message
        await crud.create_message(db, {
            "user_id": str(user.id),
            "channel": channel,
            "direction": "outgoing",
            "content": response,
            "metadata": {"intent": intent, "has_sales_data": sales_data is not None}
        })
        
        return response, {"intent": intent, "user": user_context}


message_processor = MessageProcessor()