import json
import os
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from loguru import logger

from openai import OpenAI
from langchain.chains import ConversationChain
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage

from app.config import settings
from app.utils.helpers import format_currency, format_percentage


class SalesAnalystAgent:
    """
    AI agent for analyzing sales data and responding to user queries.
    """
    
    def __init__(self):
        """Initialize the AI agent with necessary components."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.system_prompt = """
You are an expert e-commerce Sales Analyst AI assistant that helps online store owners understand their sales data.
Your goal is to provide clear, concise, and actionable insights based on their sales data.

RULES:
- NEVER use placeholder names like "Region A", "Region B", "Product X", "Product Y". Always use actual region/product names.
- NEVER report on data that is not provided to you, especially for regions or products.
- NEVER provide analyses where data is missing - instead explicitly acknowledge what data is missing.
- ONLY use the numerical data provided to you - don't fabricate numbers.
- Be precise with currency formatting (always use $x,xxx.xx format for US dollars).
- Use consistent decimal precision for percentages (always show 2 decimal places).
- If a query asks about "this month", it specifically means the current calendar month, not the last 30 days.

RESPONSE FORMAT:
1. Start with a very brief, 1-sentence summary of the key insight
2. Provide relevant metrics with specific numbers and time period
3. If available, include comparative data (vs previous period)
4. For top products/regions, list actual names with specific values
5. End with 2-3 concise, actionable recommendations 

TONE:
- Professional but conversational
- Confident in your analysis of available data
- Transparent about missing or unavailable data
- Focused on business impact rather than technical details
"""
        # Initialize LangChain components
        self.llm = ChatOpenAI(
            model_name="gpt-3.5-turbo",
            temperature=0.2,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Create a properly configured prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        
        # Create memory with correctly named variables
        self.memory = ConversationBufferMemory(
            return_messages=True, 
            memory_key="history",
            input_key="input"
        )
        
        # Configure the conversation chain
        self.chain = ConversationChain(
            llm=self.llm,
            prompt=self.prompt,
            memory=self.memory,
            verbose=False
        )
    
    def _format_currency(self, amount: float) -> str:
        """Format a number as currency."""
        return f"${float(amount):,.2f}"
    
    def _format_sales_data(self, sales_data: Dict[str, Any], top_products_limit: Optional[int] = 5) -> str:
        """
        Format sales data for including in the prompt.
        
        Args:
            sales_data: Sales data dictionary.
            top_products_limit: Maximum number of top products to include.
        
        Returns:
            str: Formatted sales data text.
        """
        formatted_text = "SALES DATA:\n"
        
        # Add time period
        time_period = sales_data.get("time_period", {})
        formatted_text += f"Period: {time_period.get('start_date', 'unknown')} to {time_period.get('end_date', 'unknown')}\n\n"
        
        # Add summary metrics
        summary = sales_data.get("summary", {})
        formatted_text += "SUMMARY:\n"
        formatted_text += f"- Total Sales: {format_currency(summary.get('total_sales', 0))}\n"
        formatted_text += f"- Total Orders: {summary.get('total_orders', 0)}\n"
        formatted_text += f"- Average Order Value: {format_currency(summary.get('average_order_value', 0))}\n"
        
        # Add conversion data if available
        conversion = sales_data.get("conversion", {})
        if conversion:
            formatted_text += f"- Online Store Sessions: {conversion.get('sessions', 0)}\n"
            formatted_text += f"- Conversion Rate: {format_percentage(conversion.get('conversion_rate', 0))}\n"
        
        # Add comparison if available
        comparison = sales_data.get("comparison", {})
        if comparison:
            formatted_text += "\nCOMPARISON TO PREVIOUS PERIOD:\n"
            formatted_text += f"- Sales Change: {format_percentage(comparison.get('sales_change', 0))} ({format_currency(comparison.get('previous_sales', 0))} previously)\n"
            formatted_text += f"- Orders Change: {format_percentage(comparison.get('orders_change', 0))} ({comparison.get('previous_orders', 0)} previously)\n"
            formatted_text += f"- AOV Change: {format_percentage(comparison.get('aov_change', 0))} ({format_currency(comparison.get('previous_aov', 0))} previously)\n"
        
        # Add growing products if available
        growing_products = sales_data.get("growing_products", [])
        if growing_products:
            formatted_text += "\nFASTEST GROWING PRODUCTS:\n"
            for i, product in enumerate(growing_products[:top_products_limit], 1):
                quantity = product.get("quantity", 0)
                revenue = product.get("revenue", 0)
                growth_rate = product.get("growth_rate", 0)
                formatted_text += f"{i}. {product.get('name', 'Unknown')}: {format_currency(revenue)} (Growth Rate: {format_percentage(growth_rate)}, {quantity} units sold)\n"
        
        # Add top products if available
        top_products = sales_data.get("top_products", [])
        if top_products:
            formatted_text += f"\nTOP {len(top_products)} PRODUCTS BY REVENUE:\n"
            for i, product in enumerate(top_products, 1):
                quantity = product.get("quantity") or product.get("units_sold") or 0
                revenue = product.get("revenue", 0)
                avg_price = revenue / quantity if quantity else 0
                formatted_text += f"{i}. {product.get('name', 'Unknown')}: {format_currency(revenue)} ({quantity} units, avg. {format_currency(avg_price)} each)\n"
        
        # Add bottom products if available
        bottom_products = sales_data.get("bottom_products", [])
        if bottom_products:
            formatted_text += "\nBOTTOM PRODUCTS BY REVENUE:\n"
            for i, product in enumerate(bottom_products[:top_products_limit], 1):
                formatted_text += f"{i}. {product.get('name', 'Unknown')}: {format_currency(product.get('revenue', 0))} ({product.get('quantity', 0)} units)\n"
        
        # Add geographic data if available
        geo_data = sales_data.get("geo_data", [])
        if geo_data:
            formatted_text += "\nGEOGRAPHIC DISTRIBUTION:\n"
            for i, country in enumerate(geo_data, 1):
                formatted_text += f"{i}. {country.get('country', 'Unknown')}: {format_currency(country.get('total_sales', 0))} ({country.get('total_orders', 0)} orders)\n"
                regions = country.get("regions", [])
                for j, region in enumerate(regions, 1):
                    formatted_text += f"   {i}.{j} {region.get('name', 'Unknown')}: {format_currency(region.get('total_sales', 0))} ({region.get('total_orders', 0)} orders)\n"
                    cities = region.get("cities", [])
                    for k, city in enumerate(cities[:3], 1):
                        formatted_text += f"      {i}.{j}.{k} {city.get('name', 'Unknown')}: {format_currency(city.get('total_sales', 0))} ({city.get('total_orders', 0)} orders)\n"
        
        # Add anomalies if available
        anomalies = sales_data.get("anomalies", [])
        if anomalies:
            formatted_text += "\nANOMALIES:\n"
            for anomaly in anomalies:
                formatted_text += f"- {anomaly.get('description', '')}\n"
        
        return formatted_text
    
    async def analyze_query(
        self, 
        query: str, 
        user_context: Dict[str, Any],
        sales_data: Optional[Dict[str, Any]] = None,
        intent: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None
    ) -> str:
        """
        Analyze a user query and generate a response.
        
        Args:
            query: User's question or command.
            user_context: Context about the user (name, store, preferences).
            sales_data: Optional sales data to include in context.
            intent: Optional dictionary of extracted query intent.
        
        Returns:
            str: Response to the user.
        """
        try:
            context_prompt = f"""
Here is context about the user and their store:
- User: {user_context.get('name', 'Store Owner')}
- Store: {user_context.get('store_name', 'E-commerce Store')}
- Platform: {user_context.get('platform', 'Shopify')}
- Timezone: {user_context.get('timezone', 'UTC')}
"""
            if intent:
                intent_prompt = f"Extracted query intent:\n{json.dumps(intent, indent=2)}"
                context_prompt += f"\n{intent_prompt}"
            
            if sales_data:
                has_geo_data = sales_data.get("geo_data") and len(sales_data.get("geo_data", [])) > 0
                has_growing_products = sales_data.get("growing_products") and len(sales_data.get("growing_products", [])) > 0
                has_declining_products = sales_data.get("declining_products") and len(sales_data.get("declining_products", [])) > 0
                
                data_availability = f"""
Data Availability Notes:
- Geographic data: {'Available' if has_geo_data else 'Not available'}
- Growing products data: {'Available' if has_growing_products else 'Not available'}
- Declining products data: {'Available' if has_declining_products else 'Not available'}
"""
                context_prompt += data_availability
                
                top_limit = 5
                if intent and isinstance(intent.get("top_products"), int):
                    top_limit = intent["top_products"]
                    
                sales_context = self._format_sales_data(sales_data, top_products_limit=top_limit)
                context_prompt += f"\n\nHere is the relevant sales data:\n{sales_context}"
                
            full_query = f"{context_prompt}\n\nUser question: {query}"
            response = self.chain.run(input=full_query)
            return response
            
        except Exception as e:
            logger.error(f"Error getting response from LangChain: {e}")
            logger.exception(e)
            # Fallback to OpenAI direct API if LangChain fails
            try:
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"{context_prompt}\n\n{query}"}
                ]
                
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=0.2
                )
                return response.choices[0].message.content
            except Exception as fallback_error:
                logger.error(f"Error in fallback to OpenAI: {fallback_error}")
                return "I'm sorry, I encountered an error while processing your request."
    
    def clear_memory(self, conversation_id: str = None):
        """
        Clear the conversation memory.
        
        Args:
            conversation_id: Conversation ID to clear (if None, clears all memory)
        """
        self.memory.clear()
        logger.info(f"Cleared conversation memory for {conversation_id or 'all conversations'}")
    
    async def generate_daily_summary(self, sales_data: Dict[str, Any], store_name: str) -> str:
        """
        Generate a daily sales summary.
        
        Args:
            sales_data: Sales data dictionary.
            store_name: Name of the store.
        
        Returns:
            str: Daily summary text.
        """
        summary_prompt = f"""
As an AI Sales Analyst, write a concise daily sales summary for {store_name}.
Be professional but conversational. Focus on the most important insights.

{self._format_sales_data(sales_data)}

Write a 3-4 paragraph summary that highlights the key metrics, any significant changes or anomalies,
and top-performing products. End with one or two brief recommendations based on the data.
"""
        
        try:
            response = self.chain.run(input=summary_prompt)
            return response
        except Exception as e:
            logger.error(f"Error generating daily summary via LangChain: {e}")
            try:
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": summary_prompt}
                ]
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    temperature=0.2
                )
                return response.choices[0].message.content
            except Exception as fallback_error:
                logger.error(f"Error in fallback to OpenAI: {fallback_error}")
                return (
                    f"Daily Sales Summary for {store_name}\n\n"
                    f"Total Sales: {format_currency(sales_data.get('summary', {}).get('total_sales', 0))}\n"
                    f"Total Orders: {sales_data.get('summary', {}).get('total_orders', 0)}\n\n"
                    "Unable to generate detailed summary at this time."
                )
    
    async def generate_anomaly_alert(self, anomaly_data: Dict[str, Any], store_name: str) -> str:
        """
        Generate an anomaly alert message.
        
        Args:
            anomaly_data: Anomaly data dictionary.
            store_name: Name of the store.
        
        Returns:
            str: Anomaly alert text.
        """
        anomaly_type = anomaly_data.get("type", "sales")
        anomaly_value = anomaly_data.get("value", 0)
        expected_value = anomaly_data.get("expected_value", 0)
        percentage_change = anomaly_data.get("percentage_change", 0)
        
        alert_prompt = f"""
As an AI Sales Analyst, write a concise anomaly alert for {store_name}.

Anomaly details:
- Type: {anomaly_type}
- Actual value: {format_currency(anomaly_value) if anomaly_type == 'sales' else anomaly_value}
- Expected value: {format_currency(expected_value) if anomaly_type == 'sales' else expected_value}
- Change: {format_percentage(percentage_change)}
- Time: {anomaly_data.get('time', 'recently')}
- Additional context: {anomaly_data.get('context', 'No additional context')}

Write a brief, clear alert (2-3 sentences) that explains the anomaly and its significance.
Start with "🚨 ALERT:" followed by a brief but informative message.
"""
        
        try:
            response = self.chain.run(input=alert_prompt)
            return response
        except Exception as e:
            logger.error(f"Error generating anomaly alert via LangChain: {e}")
            try:
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": alert_prompt}
                ]
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    temperature=0.2
                )
                return response.choices[0].message.content
            except Exception as fallback_error:
                logger.error(f"Error in fallback to OpenAI: {fallback_error}")
                return (
                    f"🚨 ALERT: Unusual {anomaly_type} detected for {store_name}. "
                    f"Current value: {format_currency(anomaly_value) if anomaly_type == 'sales' else anomaly_value}, "
                    f"expected around {format_currency(expected_value) if anomaly_type == 'sales' else expected_value} "
                    f"({format_percentage(percentage_change)} change)."
                )

# Create a singleton instance
sales_analyst_agent = SalesAnalystAgent()
