import json
import re
from typing import Dict, Any, Optional, Tuple, List, Union
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
    async def langchain_extract_intent(message_text: str) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Use LangChain to extract intent for the query.
        This version is now our primary extraction method and will return a JSON array
        if multiple sub-requests are detected.
        
        Args:
            message_text: User's query text
            
        Returns:
            A dictionary representing a single intent or a list of such dictionaries.
        """
        try:
            from langchain.chains import LLMChain
            from langchain.chat_models import ChatOpenAI
            from langchain.prompts import PromptTemplate
            from app.config import settings
            from datetime import datetime
            
            current_year = datetime.now().year
            
            # Updated prompt instructing extraction of multiple sub-requests if needed.
            template = f"""
Extract all sales analytics requests from the following compound query:
"{{query}}"

Return a JSON array where each element is an object representing one request. 
Each object must include the following fields:
- time_range: one of "today", "yesterday", "last_7_days", "last_30_days", "this_month", "custom"
- If time_range is "custom", include "specific_start_date" and "specific_end_date" in ISO 8601 format.
- primary_metric: one of "sales", "orders", "products", "customers", "geo", "conversion"
- query_type: a string indicating the type of product query requested, e.g., "top_products", "bottom_products", "fastest_growing"
- top_products_count: a number (default 5)
- include_geo_data: a boolean
- include_conversion_rate: a boolean
- comparison: a boolean
- raw_query: the original query text

VERY IMPORTANT: Always use the current year ({current_year}) for any dates unless explicitly mentioned otherwise. 

For date ranges like "March 1-8", use:
- specific_start_date: "{current_year}-03-01T00:00:00"
- specific_end_date: "{current_year}-03-08T23:59:59"

For single-day queries like "March 10 sales", use:
- specific_start_date: "{current_year}-03-10T00:00:00"
- specific_end_date: "{current_year}-03-10T23:59:59"

Always make sure end dates include the full day by using 23:59:59 as the time.

Ensure that the output is valid JSON and is an array. Do not include any markdown formatting.
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
            
            # Clean the result (remove markdown if any)
            result = result.replace("```json", "").replace("```", "").strip()
            
            intents = json.loads(result)
            # If the output is a dict (i.e. a single intent), wrap it in a list.
            if isinstance(intents, dict):
                intents = [intents]
            # For each sub-intent, store the original raw query.
            for intent in intents:
                intent["raw_query"] = message_text
                # If top_products is true and count is not provided, default to 5.
                if intent.get("top_products", False) and "top_products_count" not in intent:
                    intent["top_products_count"] = 5
            logger.info(f"LangChain extracted intents: {intents}")
            return intents
        except Exception as e:
            logger.error(f"LangChain intent extraction failed: {e}")
            # Fallback: return a default single intent based on manual extraction
            default_intent = {
                "time_range": "this_month",
                "primary_metric": "sales",
                "query_type": "top_products",
                "top_products_count": 5,
                "include_geo_data": "region" in message_text.lower() or "country" in message_text.lower(),
                "include_conversion_rate": "conversion" in message_text.lower(),
                "comparison": "compare" in message_text.lower() or "versus" in message_text.lower(),
                "raw_query": message_text
            }
            return [default_intent]
            
    @staticmethod
    async def process_message(
        db: AsyncSession,
        message_text: str,
        user_identifier: Dict[str, str],
        channel: str
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Process an incoming message and generate a response.
        Supports compound queries with multiple sub-intents.
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
            
        # Get user preferences
        timezone = "UTC"
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
        
        # Sanitize incoming message to avoid encoding issues
        safe_message_text = message_text.encode('utf-8', 'replace').decode('utf-8')
        
        # Log the incoming message (using sanitized text)
        try:
            await crud.create_message(db, {
                "user_id": str(user.id),
                "channel": channel,
                "direction": "incoming",
                "content": safe_message_text,
                "message_metadata": user_identifier
            })
            logger.debug("Logged incoming message successfully")
        except Exception as e:
            logger.error(f"Error logging incoming message: {e}")
        
        # Get the user's stores
        try:
            stores = await crud.get_stores_by_user(db, str(user.id))
            if not stores:
                logger.info(f"No stores found for user {user.id} - allowing general chat")
                store = None
            else:
                store = stores[0]
                logger.info(f"Using store: {store.name} (ID: {store.id})")
        except Exception as e:
            logger.error(f"Error getting user stores: {e}")
            store = None
        
        # Build user context based on whether store exists
        if store is not None:
            user_context = {
                "name": user.full_name or "Store Owner",
                "store_name": store.name,
                "platform": store.platform,
                "timezone": timezone,
                "has_connected_store": True
            }
        else:
            user_context = {
                "name": user.full_name or "User",
                "has_connected_store": False,
                "timezone": timezone
            }
        
        # Handle different modes based on store availability
        if store is not None:
            # SALES ANALYTICS MODE - Extract intents and process sales data
            try:
                extracted_intents = await MessageProcessor.langchain_extract_intent(message_text)
                logger.info(f"LangChain extracted intents: {extracted_intents}")
            except Exception as e:
                logger.error(f"LangChain extraction failed: {e}")
                extracted_intents = [extract_query_intent(message_text)]
                logger.info(f"Manual extraction fallback intent: {extracted_intents}")
            
            # Ensure we have a list of intents
            if not isinstance(extracted_intents, list):
                extracted_intents = [extracted_intents]
            
            # Process dates for each intent
            for intent in extracted_intents:
                # Fix the dates - convert string dates to datetime objects and update year if needed
                if intent.get("time_range") == "custom":
                    try:
                        # Handle specific_start_date
                        if "specific_start_date" in intent:
                            start_date_str = intent["specific_start_date"]
                            if isinstance(start_date_str, str):
                                import dateutil.parser
                                from datetime import datetime
                                
                                # Parse the date string
                                try:
                                    start_date = dateutil.parser.parse(start_date_str)
                                    
                                    # Update year to current year if it's not the current year
                                    current_year = datetime.now().year
                                    if start_date.year != current_year:
                                        start_date = start_date.replace(year=current_year)
                                    
                                    # Convert to datetime object
                                    intent["specific_start_date"] = start_date
                                    logger.info(f"Converted start date to: {start_date}")
                                except Exception as parse_error:
                                    logger.error(f"Error parsing start date: {parse_error}")
                                    intent["specific_start_date"] = None
                        
                        # Handle specific_end_date
                        if "specific_end_date" in intent:
                            end_date_str = intent["specific_end_date"]
                            if isinstance(end_date_str, str):
                                import dateutil.parser
                                from datetime import datetime, time
                                
                                # Parse the date string
                                try:
                                    end_date = dateutil.parser.parse(end_date_str)
                                    
                                    # Update year to current year if it's not the current year
                                    current_year = datetime.now().year
                                    if end_date.year != current_year:
                                        end_date = end_date.replace(year=current_year)
                                    
                                    # Make sure end_date includes the whole day if time is midnight
                                    if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
                                        end_date = datetime.combine(end_date.date(), time(23, 59, 59, 999999))
                                    
                                    # Convert to datetime object
                                    intent["specific_end_date"] = end_date
                                    logger.info(f"Converted end date to: {end_date}")
                                except Exception as parse_error:
                                    logger.error(f"Error parsing end date: {parse_error}")
                                    intent["specific_end_date"] = None
                    except Exception as e:
                        logger.error(f"Error processing dates for intent: {e}")
            
            # Process each intent individually and collect responses
            responses = []
            for intent in extracted_intents:
                # Fetch sales data using the intent's parameters
                try:
                    # Get the specific dates
                    specific_start = intent.get("specific_start_date")
                    specific_end = intent.get("specific_end_date")
                    
                    # Pass them to get_sales_data
                    sales_data = await get_sales_data(
                        db,
                        str(store.id),
                        intent["time_range"],
                        user_context["timezone"],
                        include_geo_data=intent.get("include_geo_data", False),
                        top_products_limit=intent.get("top_products_count", 10),
                        bottom_products_limit=intent.get("top_products_count", 10),
                        query_type=intent.get("query_type", "top_products"),
                        specific_start_date=specific_start,
                        specific_end_date=specific_end
                    )
                    
                    # Update intent with additional info if needed
                    if sales_data:
                        intent["actual_top_products_count"] = len(sales_data.get("top_products", []))
                        intent["geo_regions_count"] = len(sales_data.get("geo_data", []))
                        logger.info(f"Retrieved sales data for {intent.get('time_range')}: {sales_data.get('time_period', {}).get('start_date')} to {sales_data.get('time_period', {}).get('end_date')}")
                except Exception as e:
                    logger.error(f"Error getting sales data: {e}")
                    sales_data = None

                # Generate AI response for this sub-intent
                try:
                    sub_response = await sales_analyst_agent.analyze_query(
                        query=message_text,
                        user_context=user_context,
                        sales_data=sales_data,
                        intent=intent,
                        conversation_id=conversation_id
                    )
                    responses.append(sub_response)
                except Exception as e:
                    logger.error(f"Error generating response for intent {intent}: {e}")
                    responses.append("I'm sorry, I encountered an error processing this part of your request.")
            
            # Combine responses from all sub-intents
            final_response = "\n\n".join(responses)
            
            # Log outgoing message with JSON-serializable metadata
            try:
                message_metadata = {"intents": extracted_intents, "has_sales_data": sales_data is not None}
                metadata_serializable = json.loads(json.dumps(message_metadata, default=str))
                await crud.create_message(db, {
                    "user_id": str(user.id),
                    "channel": channel,
                    "direction": "outgoing",
                    "content": final_response,
                    "message_metadata": metadata_serializable
                })
                logger.debug("Logged outgoing message successfully")
            except Exception as e:
                logger.error(f"Error logging outgoing message: {e}")
            
            return final_response, {"intents": extracted_intents, "user": user_context}
        
        else:
            # GENERAL CHAT MODE - No store connected, skip intent extraction
            logger.info("Processing as general chat - no sales analysis")
            
            try:
                # Simple AI response without sales context or intent extraction
                final_response = await sales_analyst_agent.analyze_query(
                    query=message_text,
                    user_context=user_context,
                    sales_data=None,  # No sales data
                    intent=None,      # No intent extraction
                    conversation_id=conversation_id
                )
                
                # Log outgoing message
                try:
                    await crud.create_message(db, {
                        "user_id": str(user.id),
                        "channel": channel,
                        "direction": "outgoing",
                        "content": final_response,
                        "message_metadata": {"mode": "general_chat", "has_sales_data": False}
                    })
                    logger.debug("Logged outgoing message successfully")
                except Exception as e:
                    logger.error(f"Error logging outgoing message: {e}")
                
                return final_response, {"mode": "general_chat", "user": user_context}
                
            except Exception as e:
                logger.error(f"Error generating general chat response: {e}")
                return "I'm here to help! Feel free to ask me anything, or if you'd like to analyze sales data, you can connect a store first.", None
    
    @staticmethod
    async def clear_user_memory(user_identifier: Dict[str, str], channel: str):
        """
        Clear the conversation memory for a specific user.
        """
        conversation_id = None
        if channel == "slack" and "slack_id" in user_identifier:
            conversation_id = f"slack_{user_identifier['slack_id']}"
        elif channel == "whatsapp" and "whatsapp_number" in user_identifier:
            conversation_id = f"whatsapp_{user_identifier['whatsapp_number']}"
        elif (channel == "email" or channel == "test") and "email" in user_identifier:
            conversation_id = f"email_{user_identifier['email']}"
            
        if conversation_id:
            sales_analyst_agent.clear_memory(conversation_id)
            logger.info(f"Cleared conversation memory for {conversation_id}")
            return True
        else:
            logger.error(f"Could not determine conversation ID for {channel} user: {user_identifier}")
            return False


message_processor = MessageProcessor()