import json
import re
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.agent import sales_analyst_agent
from app.db import crud
from app.db.models import User, Store, UserPreference, Message
from app.utils.helpers import extract_query_intent
from app.services.analytics import get_sales_data


class MessageProcessor:
    """
    Process incoming messages from different channels and coordinate responses.
    """
    
    @staticmethod
    async def langchain_extract_intent(message_text: str) -> Dict[str, Any]:
        """
        Use LangChain to extract intent when pattern matching fails.
        This serves as a more sophisticated fallback for intent extraction.
        
        Args:
            message_text: User's query text
            
        Returns:
            dict: Structured intent data
        """
        try:
            from langchain.chains import LLMChain
            from langchain.chat_models import ChatOpenAI
            from langchain.prompts import PromptTemplate
            from app.config import settings
            
            template = """
            Extract the sales analytics intent from this query:
            "{query}"
            
            Return a JSON with the following fields:
            - time_range: (today, yesterday, last_7_days, last_30_days, this_month, last_month, or specific_month_YYYY_MM)
            - primary_metric: (sales, orders, products, customers, geo, conversion)
            - top_products: (boolean)
            - top_products_count: (number, default 5)
            - bottom_products: (boolean)
            - include_geo_data: (boolean)
            - include_conversion_rate: (boolean)
            - comparison: (boolean)
            
            Response should be valid JSON only:
            """
            
            prompt = PromptTemplate(
                input_variables=["query"],
                template=template,
            )
            
            llm = ChatOpenAI(
                model_name="gpt-3.5-turbo",
                temperature=0,
                api_key=settings.OPENAI_API_KEY
            )
            
            chain = LLMChain(llm=llm, prompt=prompt)
            result = chain.run(query=message_text)
            
            # Clean the result - sometimes the model returns markdown
            result = result.replace("```json", "").replace("```", "").strip()
            
            # Parse the result as JSON
            intent = json.loads(result)
            
            # Make sure required fields are present
            intent["raw_query"] = message_text
            
            # Ensure we have top_products_count if top_products is True
            if intent.get("top_products", False) and "top_products_count" not in intent:
                intent["top_products_count"] = 5
                
            logger.info(f"LangChain extracted intent: {intent}")
            return intent
        except Exception as e:
            logger.error(f"LangChain intent extraction failed: {e}")
            # Return a default intent if LangChain fails
            return {
                "time_range": "this_month",  # Default to current month, not just 7 days
                "primary_metric": "sales",
                "top_products": any(phrase in message_text.lower() for phrase in ["top products", "best selling"]),
                "top_products_count": 5,
                "bottom_products": False,
                "include_geo_data": "region" in message_text.lower() or "country" in message_text.lower(),
                "include_conversion_rate": "conversion" in message_text.lower(),
                "comparison": "compare" in message_text.lower() or "versus" in message_text.lower(),
                "raw_query": message_text
            }
    
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
        conversation_id = None
        try:
            if channel == "slack" and "slack_id" in user_identifier:
                user = await crud.get_user_by_slack_id(db, user_identifier["slack_id"])
                conversation_id = f"slack_{user_identifier['slack_id']}"
                logger.debug(f"Looking up user by slack_id: {user_identifier['slack_id']}")
            elif channel == "whatsapp" and "whatsapp_number" in user_identifier:
                user = await crud.get_user_by_whatsapp(db, user_identifier["whatsapp_number"])
                conversation_id = f"whatsapp_{user_identifier['whatsapp_number']}"
                logger.debug(f"Looking up user by whatsapp_number: {user_identifier['whatsapp_number']}")
            elif (channel == "email" or channel == "test") and "email" in user_identifier:
                user = await crud.get_user_by_email(db, user_identifier["email"])
                conversation_id = f"email_{user_identifier['email']}"
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
                "message_metadata": user_identifier
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
        
        # Extract intent from the message - with multi-level fallbacks
        try:
            intent = extract_query_intent(message_text)
            logger.info(f"Regular pattern matching extracted intent: {intent}")
        except Exception as e:
            logger.error(f"Error in regular intent extraction: {e}")
            try:
                # Try LangChain fallback for more sophisticated intent extraction
                intent = await MessageProcessor.langchain_extract_intent(message_text)
                logger.info(f"LangChain fallback extracted intent: {intent}")
            except Exception as le:
                logger.error(f"LangChain fallback also failed: {le}")
                # Ultimate fallback with better defaults
                now = datetime.now()
                intent = {
                    "time_range": f"specific_month_{now.year}_{now.month:02d}",  # Default to current month
                    "primary_metric": "sales",
                    "top_products": any(phrase in message_text.lower() for phrase in ["top products", "best selling", "bestseller"]),
                    "top_products_count": 5,
                    "bottom_products": any(phrase in message_text.lower() for phrase in ["worst", "bottom", "poorest"]),
                    "include_geo_data": "region" in message_text.lower() or "country" in message_text.lower(),
                    "include_conversion_rate": "conversion" in message_text.lower(),
                    "comparison": "compare" in message_text.lower() or "versus" in message_text.lower() or " vs " in message_text.lower(),
                    "raw_query": message_text
                }
                logger.info(f"Using ultimate fallback intent: {intent}")
        
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
            # Check if we need geographic data
            include_geo = intent.get("include_geo_data", False) or "region" in message_text.lower() or "country" in message_text.lower()
            
            # Check for top products count in the query
            # First priority: explicit numbers in the query
            top_products_count = None
            top_pattern = re.search(r"top\s+(\d+)", message_text.lower())
            if top_pattern:
                try:
                    top_products_count = int(top_pattern.group(1))
                    intent["top_products_count"] = top_products_count  # Update intent
                    logger.info(f"Extracted top_products_count={top_products_count} from explicit query")
                except ValueError:
                    pass
            
            # Second priority: intent's top_products_count
            if top_products_count is None:
                top_products_count = intent.get("top_products_count", 5)
            
            # Ensure we mark this as a top products query if a count is specified
            if top_products_count and top_products_count > 0:
                intent["top_products"] = True
            
            # Always try to get sales data regardless of keywords
            logger.info(f"Fetching sales data for time range: {intent['time_range']}")
            sales_data = await get_sales_data(
                db, 
                str(store.id), 
                intent["time_range"],
                user_context["timezone"],
                include_geo_data=include_geo,
                top_products_limit=top_products_count
            )
            
            if sales_data:
                # Add the requested top products count to sales data for reference
                sales_data["top_products_count"] = top_products_count
                
                # Log a summary of the retrieved data
                summary = sales_data.get("summary", {})
                time_period = sales_data.get("time_period", {})
                actual_top_products = sales_data.get("top_products", [])
                geo_regions_count = len(sales_data.get("geo_data", []))
                
                # Update intent with actual counts for context
                intent["actual_top_products_count"] = len(actual_top_products)
                intent["geo_regions_count"] = geo_regions_count
                
                logger.info(f"Retrieved sales data for {time_period.get('range_type')}: "
                            f"{time_period.get('start_date')} to {time_period.get('end_date')}")
                logger.info(f"Sales summary: Total sales: {summary.get('total_sales')}, "
                            f"Orders: {summary.get('total_orders')}, "
                            f"Top Products: {len(actual_top_products)}, "
                            f"Geographic Regions: {geo_regions_count}")
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
            
            # Pass conversation_id to the agent to maintain per-user memory
            response = await sales_analyst_agent.analyze_query(
                query=message_text,
                user_context=user_context,
                sales_data=sales_data,
                intent=intent,
                conversation_id=conversation_id
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
                "message_metadata": {"intent": intent, "has_sales_data": sales_data is not None}
            })
            logger.debug("Logged outgoing message successfully")
        except Exception as e:
            logger.error(f"Error logging outgoing message: {e}")
            # Continue even if message logging fails
        
        return response, {"intent": intent, "user": user_context}
    
    @staticmethod
    async def clear_user_memory(user_identifier: Dict[str, str], channel: str):
        """
        Clear the conversation memory for a specific user.
        
        Args:
            user_identifier: Dictionary with user identifier
            channel: The communication channel
        """
        conversation_id = None
        
        if channel == "slack" and "slack_id" in user_identifier:
            conversation_id = f"slack_{user_identifier['slack_id']}"
        elif channel == "whatsapp" and "whatsapp_number" in user_identifier:
            conversation_id = f"whatsapp_{user_identifier['whatsapp_number']}"
        elif (channel == "email" or channel == "test") and "email" in user_identifier:
            conversation_id = f"email_{user_identifier['email']}"
            
        if conversation_id:
            # Clear specific conversation memory
            sales_analyst_agent.clear_memory(conversation_id)
            logger.info(f"Cleared conversation memory for {conversation_id}")
            return True
        else:
            # If no conversation ID could be determined, log an error
            logger.error(f"Could not determine conversation ID for {channel} user: {user_identifier}")
            return False


message_processor = MessageProcessor()