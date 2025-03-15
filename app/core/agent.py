import json
import os
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from loguru import logger

from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.schema import HumanMessage, SystemMessage, AIMessage

from app.config import settings
from app.utils.helpers import format_currency, format_percentage


class SalesAnalystAgent:
    """
    AI agent for analyzing sales data and responding to user queries.
    """
    
    def __init__(self):
        """Initialize the AI agent with necessary components."""
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.2,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Define system prompt for the agent
        self.system_prompt = """
        You are an expert e-commerce Sales Analyst AI assistant that helps online store owners understand their sales data.
        Your goal is to provide clear, concise, and actionable insights based on their sales data.
        
        Here are some guidelines for your responses:
        - Be concise but informative
        - Highlight the most important trends and insights
        - Use a friendly, professional tone
        - Provide specific numbers and percentages when available
        - End with actionable recommendations when appropriate
        - If you don't have enough information, ask clarifying questions
        - Format currency values and percentages consistently
        """
    
    async def analyze_query(self, 
                      query: str, 
                      user_context: Dict[str, Any],
                      sales_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Analyze a user query and generate a response.
        
        Args:
            query: User's question or command
            user_context: Context about the user (name, store, preferences)
            sales_data: Optional sales data to include in context
        
        Returns:
            str: Response to the user
        """
        # Build message history
        messages = [
            SystemMessage(content=self.system_prompt),
        ]
        
        # Add user context
        context_prompt = f"""
        Here is context about the user and their store:
        - User: {user_context.get('name', 'Store Owner')}
        - Store: {user_context.get('store_name', 'E-commerce Store')}
        - Platform: {user_context.get('platform', 'Shopify')}
        - Timezone: {user_context.get('timezone', 'UTC')}
        """
        
        messages.append(SystemMessage(content=context_prompt))
        
        # Add sales data if available
        if sales_data:
            sales_context = self._format_sales_data(sales_data)
            messages.append(SystemMessage(content=f"Here is the relevant sales data:\n{sales_context}"))
        
        # Add user query
        messages.append(HumanMessage(content=query))
        
        try:
            # Get response from LLM
            response = self.llm(messages)
            return response.content
        except Exception as e:
            logger.error(f"Error getting response from LLM: {e}")
            return "I'm sorry, I encountered an error while analyzing your request. Please try again later."
    
    def _format_sales_data(self, sales_data: Dict[str, Any]) -> str:
        """
        Format sales data for including in the prompt.
        
        Args:
            sales_data: Sales data dictionary
        
        Returns:
            str: Formatted sales data text
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
        
        # Add comparison if available
        comparison = sales_data.get("comparison", {})
        if comparison:
            formatted_text += "\nCOMPARISON TO PREVIOUS PERIOD:\n"
            formatted_text += f"- Sales Change: {format_percentage(comparison.get('sales_change', 0))} ({format_currency(comparison.get('previous_sales', 0))} previously)\n"
            formatted_text += f"- Orders Change: {format_percentage(comparison.get('orders_change', 0))} ({comparison.get('previous_orders', 0)} previously)\n"
            formatted_text += f"- AOV Change: {format_percentage(comparison.get('aov_change', 0))} ({format_currency(comparison.get('previous_aov', 0))} previously)\n"
        
        # Add top products if available
        top_products = sales_data.get("top_products", [])
        if top_products:
            formatted_text += "\nTOP PRODUCTS:\n"
            for i, product in enumerate(top_products[:5], 1):
                formatted_text += f"{i}. {product.get('name', 'Unknown')}: {format_currency(product.get('revenue', 0))} ({product.get('quantity', 0)} units)\n"
        
        # Add anomalies if available
        anomalies = sales_data.get("anomalies", [])
        if anomalies:
            formatted_text += "\nANOMALIES:\n"
            for anomaly in anomalies:
                formatted_text += f"- {anomaly.get('description', '')}\n"
        
        return formatted_text
    
    async def generate_daily_summary(self, sales_data: Dict[str, Any], store_name: str) -> str:
        """
        Generate a daily sales summary.
        
        Args:
            sales_data: Sales data dictionary
            store_name: Name of the store
        
        Returns:
            str: Daily summary text
        """
        summary_prompt = f"""
        As an AI Sales Analyst, write a concise daily sales summary for {store_name}.
        Be professional but conversational. Focus on the most important insights.
        
        {self._format_sales_data(sales_data)}
        
        Write a 3-4 paragraph summary that highlights the key metrics, any significant changes or anomalies,
        and top-performing products. End with one or two brief recommendations based on the data.
        """
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=summary_prompt)
        ]
        
        try:
            response = self.llm(messages)
            return response.content
        except Exception as e:
            logger.error(f"Error generating daily summary: {e}")
            return f"Daily Sales Summary for {store_name}\n\nTotal Sales: {format_currency(sales_data.get('summary', {}).get('total_sales', 0))}\nTotal Orders: {sales_data.get('summary', {}).get('total_orders', 0)}\n\nUnable to generate detailed summary at this time."
    
    async def generate_anomaly_alert(self, anomaly_data: Dict[str, Any], store_name: str) -> str:
        """
        Generate an anomaly alert message.
        
        Args:
            anomaly_data: Anomaly data dictionary
            store_name: Name of the store
        
        Returns:
            str: Anomaly alert text
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
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=alert_prompt)
        ]
        
        try:
            response = self.llm(messages)
            return response.content
        except Exception as e:
            logger.error(f"Error generating anomaly alert: {e}")
            return f"🚨 ALERT: Unusual {anomaly_type} detected for {store_name}. Current value: {format_currency(anomaly_value) if anomaly_type == 'sales' else anomaly_value}, expected around {format_currency(expected_value) if anomaly_type == 'sales' else expected_value} ({format_percentage(percentage_change)} change)."


# Create a singleton instance
sales_analyst_agent = SalesAnalystAgent()