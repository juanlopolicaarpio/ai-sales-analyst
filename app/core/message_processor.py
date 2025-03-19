import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.agent import sales_analyst_agent
from app.db import crud
from app.db.models import User, Store, UserPreference
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
            channel: The channel (slack, whatsapp, email, test)
        
        Returns:
            tuple: (response_text, metadata)
        """
        # Find the user based on the channel and identifier
        user = None
        try:
            if channel == "slack" and "slack_id" in user_identifier:
                user = await crud.get_user_by_slack_id(db, user_identifier["slack_id"])
                logger.debug(f"Looking up user by slack_id: {user_identifier['slack_id']}")
            elif channel == "whatsapp" and "whatsapp_number" in user_identifier:
                user = await crud.get_user_by_whatsapp(db, user_identifier["whatsapp_number"])
                logger.debug(f"Looking up user by whatsapp_number: {user_identifier['whatsapp_number']}")
            elif (channel == "email" or channel == "test") and "email" in user_identifier:
                user = await crud.get_user_by_email(db, user_identifier["email"])
                logger.debug(f"Looking up user by email: {user_identifier['email']}")
            
            if not user:
                logger.warning(f"Unknown user tried to send message via {channel}: {user_identifier}")
                return "I don't recognize you as an authorized user. Please contact your administrator to set up your account.", None
        except Exception as e:
            logger.error(f"Error finding user: {e}")
            return "I encountered an error while identifying your user account. Please try again later or contact support.", None
            
        # Get user preferences explicitly rather than using lazy loading
        timezone = "UTC"  # Default timezone
        try:
            preferences_result = await db.execute(
                select(UserPreference).where(UserPreference.user_id == user.id)
            )
            user_preferences = preferences_result.scalars().first()
            if user_preferences:
                timezone = user_preferences.timezone or "UTC"
                logger.debug(f"Using timezone: {timezone}")
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            # Continue with default timezone
        
        # Log the incoming message
        try:
            await crud.create_message(db, {
                "user_id": str(user.id),
                "channel": channel,
                "direction": "incoming",
                "content": message_text,
                "message_metadata": user_identifier  # Fixed field name from metadata to message_metadata
            })
            logger.debug("Logged incoming message successfully")
        except Exception as e:
            logger.error(f"Error logging incoming message: {e}")
            # Continue even if message logging fails
        
        # Get the user's stores
        try:
            stores = await crud.get_stores_by_user(db, str(user.id))
            if not stores:
                logger.warning(f"No stores found for user {user.id}")
                return "I couldn't find any connected stores for your account. Please set up at least one store to get started.", None
            
            # For simplicity, use the first store
            store = stores[0]
            logger.info(f"Using store: {store.name} (ID: {store.id})")
        except Exception as e:
            logger.error(f"Error getting user stores: {e}")
            return "I encountered an error while accessing your store information. Please try again later or contact support.", None
        
        # Extract intent from the message
        try:
            intent = extract_query_intent(message_text)
            logger.info(f"Extracted intent: {intent}")
        except Exception as e:
            logger.error(f"Error extracting intent: {e}")
            intent = {
            "time_range": "last_7_days",
            "primary_metric": "sales",
            "top_products": any(phrase in message_text.lower() for phrase in ["top products", "best selling"]),
            "bottom_products": any(phrase in message_text.lower() for phrase in ["bottom products", "worst selling"]),
            "include_geo_data": False,
            "include_conversion_rate": False,
            "comparison": False,
            "specific_start_date": None,
            "specific_end_date": None,
            "raw_query": message_text
            }
            logger.info(f"Using fallback intent: {intent}")
        
        # Get user context
        user_context = {
            "name": user.full_name or "Store Owner",
            "store_name": store.name,
            "platform": store.platform,
            "timezone": timezone
        }
        
        # Get relevant sales data based on the intent
        sales_data = None
        try:
            # Always try to get sales data regardless of keywords
            logger.info(f"Fetching sales data for time range: {intent['time_range']}")
            sales_data = await get_sales_data(
                db, 
                str(store.id), 
                intent["time_range"],
                user_context["timezone"],
                include_geo_data=intent.get("include_geo_data", False),
                include_conversion_rate=intent.get("include_conversion_rate", False),
                specific_start_date=intent.get("specific_start_date"),
                specific_end_date=intent.get("specific_end_date")
        
            )
            
            if sales_data:
                # Log a summary of the retrieved data
                summary = sales_data.get("summary", {})
                time_period = sales_data.get("time_period", {})
                top_products_count = len(sales_data.get("top_products", []))
                
                logger.info(f"Retrieved sales data for {time_period.get('range_type')}: "
                            f"{time_period.get('start_date')} to {time_period.get('end_date')}")
                logger.info(f"Sales summary: Total sales: {summary.get('total_sales')}, "
                            f"Orders: {summary.get('total_orders')}, "
                            f"Top Products: {top_products_count}")
            else:
                logger.warning(f"No sales data retrieved for time range: {intent['time_range']}")
        except Exception as e:
            logger.error(f"Error getting sales data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Continue without sales data
        
        # Use AI agent to generate response
        try:
            logger.info(f"Generating AI response with {'sales data' if sales_data else 'no sales data'}")
            response = await sales_analyst_agent.analyze_query(
                query=message_text,
                user_context=user_context,
                sales_data=sales_data
            )
            logger.debug(f"AI response generated: {response[:100]}...")
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            import traceback
            logger.error(traceback.format_exc())
            response = "I'm sorry, I encountered an error while processing your request. Please try again later."
        
        # Log the outgoing message
        try:
            await crud.create_message(db, {
                "user_id": str(user.id),
                "channel": channel,
                "direction": "outgoing",
                "content": response,
                "message_metadata": {"intent": intent, "has_sales_data": sales_data is not None}  # Fixed field name
            })
            logger.debug("Logged outgoing message successfully")
        except Exception as e:
            logger.error(f"Error logging outgoing message: {e}")
            # Continue even if message logging fails
        
        return response, {"intent": intent, "user": user_context}


message_processor = MessageProcessor()