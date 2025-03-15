import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import pandas as pd
import numpy as np
from scipy import stats

from app.db import crud, models
from app.core.agent import sales_analyst_agent


async def detect_anomalies(
    db: AsyncSession,
    store_id: str,
    lookback_days: int = 30
) -> List[Dict[str, Any]]:
    """
    Detect sales anomalies for a store.
    
    Args:
        db: Database session
        store_id: Store ID
        lookback_days: Number of days to look back for anomaly detection
    
    Returns:
        list: List of detected anomalies
    """
    # Get all orders within the lookback period
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    
    orders = await crud.get_orders_by_date_range(db, store_id, start_date, end_date)
    
    # If not enough data, return empty list
    if len(orders) < 10:  # Need a minimum amount of data for meaningful detection
        logger.warning(f"Not enough order data for anomaly detection for store {store_id}")
        return []
    
    # Convert to DataFrame for analysis
    orders_df = pd.DataFrame([
        {
            "order_id": str(order.id),
            "order_date": order.order_date,
            "total_price": order.total_price,
            "order_number": order.order_number
        }
        for order in orders
    ])
    
    # Add datetime components for time-based analysis
    orders_df["date"] = orders_df["order_date"].dt.date
    orders_df["hour"] = orders_df["order_date"].dt.hour
    orders_df["day_of_week"] = orders_df["order_date"].dt.dayofweek
    
    # Detect anomalies in daily sales
    daily_anomalies = await _detect_daily_sales_anomalies(db, store_id, orders_df)
    
    # Detect anomalies in hourly order rates
    hourly_anomalies = await _detect_hourly_order_anomalies(db, store_id, orders_df)
    
    # Detect anomalies in average order value
    aov_anomalies = await _detect_aov_anomalies(db, store_id, orders_df)
    
    # Combine all anomalies
    all_anomalies = daily_anomalies + hourly_anomalies + aov_anomalies
    
    # Create insight records for anomalies
    for anomaly in all_anomalies:
        insight_data = {
            "store_id": store_id,
            "insight_type": "anomaly",
            "title": anomaly["title"],
            "description": anomaly["description"],
            "metrics": anomaly["metrics"],
            "is_anomaly": True,
            "severity": anomaly["severity"],
            "insight_date": datetime.utcnow(),
            "is_sent": False
        }
        await crud.create_insight(db, insight_data)
    
    return all_anomalies


async def _detect_daily_sales_anomalies(
    db: AsyncSession,
    store_id: str,
    orders_df: pd.DataFrame
) -> List[Dict[str, Any]]:
    """
    Detect anomalies in daily sales.
    
    Args:
        db: Database session
        store_id: Store ID
        orders_df: DataFrame of orders
    
    Returns:
        list: List of detected anomalies
    """
    # Group by date and calculate daily sales
    daily_sales = orders_df.groupby("date")["total_price"].sum().reset_index()
    
    # Need at least a few days of data
    if len(daily_sales) < 5:
        return []
    
    # Calculate rolling mean and standard deviation (excluding the current day)
    # Use a 7-day window but exclude the current day
    rolling_stats = daily_sales["total_price"].rolling(window=7, min_periods=5).agg(['mean', 'std'])
    
    # Calculate z-scores
    daily_sales["mean"] = rolling_stats["mean"].shift(1)  # Use previous days' mean
    daily_sales["std"] = rolling_stats["std"].shift(1)    # Use previous days' std
    
    # Handle case where std is 0 or NaN
    daily_sales["std"] = daily_sales["std"].replace(0, daily_sales["mean"] * 0.1)  # Set minimum std as 10% of mean
    daily_sales["std"] = daily_sales["std"].fillna(daily_sales["total_price"].std())  # Use overall std if NaN
    
    # Calculate z-scores
    daily_sales["z_score"] = (daily_sales["total_price"] - daily_sales["mean"]) / daily_sales["std"]
    
    # Identify anomalies (|z-score| > 2)
    anomalies = daily_sales[abs(daily_sales["z_score"]) > 2].copy()
    
    # Format anomalies for return
    result = []
    for _, row in anomalies.iterrows():
        # Skip anomalies from more than 7 days ago
        if (datetime.now().date() - row["date"]) > timedelta(days=7):
            continue
            
        anomaly_type = "unusually_high_sales" if row["z_score"] > 0 else "unusually_low_sales"
        
        # Calculate percentage difference from expected
        pct_diff = (row["total_price"] - row["mean"]) / row["mean"] if row["mean"] > 0 else 0
        
        # Determine severity (1-5)
        severity = min(5, max(1, int(abs(row["z_score"]))))
        
        anomaly = {
            "type": anomaly_type,
            "date": row["date"].strftime("%Y-%m-%d"),
            "value": float(row["total_price"]),
            "expected_value": float(row["mean"]),
            "z_score": float(row["z_score"]),
            "percentage_change": float(pct_diff),
            "severity": severity,
            "title": f"{'High' if row['z_score'] > 0 else 'Low'} Sales Anomaly Detected",
            "description": f"Sales on {row['date'].strftime('%Y-%m-%d')} were {abs(pct_diff)*100:.1f}% {'higher' if pct_diff > 0 else 'lower'} than expected.",
            "metrics": {
                "actual_sales": float(row["total_price"]),
                "expected_sales": float(row["mean"]),
                "z_score": float(row["z_score"]),
                "percentage_difference": float(pct_diff),
            }
        }
        result.append(anomaly)
    
    return result


async def _detect_hourly_order_anomalies(
    db: AsyncSession,
    store_id: str,
    orders_df: pd.DataFrame
) -> List[Dict[str, Any]]:
    """
    Detect anomalies in hourly order rates.
    
    Args:
        db: Database session
        store_id: Store ID
        orders_df: DataFrame of orders
    
    Returns:
        list: List of detected anomalies
    """
    # Only look at recent orders (last 48 hours)
    recent_cutoff = datetime.utcnow() - timedelta(hours=48)
    recent_orders = orders_df[orders_df["order_date"] >= recent_cutoff].copy()
    
    if len(recent_orders) < 5:  # Not enough recent data
        return []
    
    # Group by hour and calculate order counts
    recent_orders["hour_bin"] = recent_orders["order_date"].dt.floor("H")
    hourly_orders = recent_orders.groupby("hour_bin").size().reset_index(name="count")
    
    # Get historical hourly patterns (for each hour of the day)
    all_orders = orders_df.copy()
    all_orders["hour"] = all_orders["order_date"].dt.hour
    all_orders["day_of_week"] = all_orders["order_date"].dt.dayofweek
    
    # Calculate expected order counts by hour and day of week
    hour_day_stats = all_orders.groupby(["hour", "day_of_week"]).size().reset_index(name="historical_count")
    
    # Join with recent hourly data
    hourly_orders["hour"] = hourly_orders["hour_bin"].dt.hour
    hourly_orders["day_of_week"] = hourly_orders["hour_bin"].dt.dayofweek
    hourly_orders = hourly_orders.merge(hour_day_stats, on=["hour", "day_of_week"], how="left")
    
    # Calculate z-scores based on historical patterns
    # Assume Poisson distribution for order counts
    hourly_orders["expected"] = hourly_orders["historical_count"] / (len(all_orders["date"].unique()) / 7)
    hourly_orders["expected"] = hourly_orders["expected"].fillna(hourly_orders["count"].mean())
    
    # Use Poisson PMF to calculate probability
    hourly_orders["p_value"] = hourly_orders.apply(
        lambda row: 1 - stats.poisson.cdf(row["count"], row["expected"]) 
        if row["count"] > row["expected"] 
        else stats.poisson.cdf(row["count"], row["expected"]),
        axis=1
    )
    
    # Identify anomalies (p < 0.05)
    anomalies = hourly_orders[hourly_orders["p_value"] < 0.05].copy()
    
    # Only include anomalies from the last 12 hours
    recent_anomaly_cutoff = datetime.utcnow() - timedelta(hours=12)
    anomalies = anomalies[anomalies["hour_bin"] >= recent_anomaly_cutoff]
    
    # Format anomalies for return
    result = []
    for _, row in anomalies.iterrows():
        anomaly_type = "unusually_high_orders" if row["count"] > row["expected"] else "unusually_low_orders"
        
        # Calculate percentage difference from expected
        pct_diff = (row["count"] - row["expected"]) / row["expected"] if row["expected"] > 0 else 0
        
        # Determine severity (1-5)
        if row["p_value"] < 0.001:
            severity = 5
        elif row["p_value"] < 0.01:
            severity = 4
        elif row["p_value"] < 0.05:
            severity = 3
        else:
            severity = 2
        
        # Only include significant anomalies (high severity or large percentage change)
        if severity < 3 and abs(pct_diff) < 0.5:  # Less than 50% change
            continue
        
        anomaly = {
            "type": anomaly_type,
            "hour_bin": row["hour_bin"].strftime("%Y-%m-%d %H:00"),
            "value": int(row["count"]),
            "expected_value": float(row["expected"]),
            "p_value": float(row["p_value"]),
            "percentage_change": float(pct_diff),
            "severity": severity,
            "title": f"{'High' if row['count'] > row['expected'] else 'Low'} Order Rate Anomaly",
            "description": f"Order count for {row['hour_bin'].strftime('%Y-%m-%d %H:00')} was {abs(pct_diff)*100:.1f}% {'higher' if pct_diff > 0 else 'lower'} than expected.",
            "metrics": {
                "actual_orders": int(row["count"]),
                "expected_orders": float(row["expected"]),
                "p_value": float(row["p_value"]),
                "percentage_difference": float(pct_diff),
            }
        }
        result.append(anomaly)
    
    return result


async def _detect_aov_anomalies(
    db: AsyncSession,
    store_id: str,
    orders_df: pd.DataFrame
) -> List[Dict[str, Any]]:
    """
    Detect anomalies in average order value.
    
    Args:
        db: Database session
        store_id: Store ID
        orders_df: DataFrame of orders
    
    Returns:
        list: List of detected anomalies
    """
    # Group by date and calculate daily AOV
    daily_aov = orders_df.groupby("date").agg(
        total_sales=("total_price", "sum"),
        order_count=("order_id", "count")
    ).reset_index()
    
    daily_aov["aov"] = daily_aov["total_sales"] / daily_aov["order_count"]
    
    # Need at least a few days of data
    if len(daily_aov) < 5:
        return []
    
    # Calculate rolling mean and standard deviation (excluding the current day)
    rolling_stats = daily_aov["aov"].rolling(window=7, min_periods=5).agg(['mean', 'std'])
    
    # Calculate z-scores
    daily_aov["mean"] = rolling_stats["mean"].shift(1)  # Use previous days' mean
    daily_aov["std"] = rolling_stats["std"].shift(1)    # Use previous days' std
    
    # Handle case where std is 0 or NaN
    daily_aov["std"] = daily_aov["std"].replace(0, daily_aov["mean"] * 0.1)  # Set minimum std as 10% of mean
    daily_aov["std"] = daily_aov["std"].fillna(daily_aov["aov"].std())  # Use overall std if NaN
    
    # Calculate z-scores
    daily_aov["z_score"] = (daily_aov["aov"] - daily_aov["mean"]) / daily_aov["std"]
    
    # Identify anomalies (|z-score| > 2.5) - Using a higher threshold for AOV anomalies
    anomalies = daily_aov[abs(daily_aov["z_score"]) > 2.5].copy()
    
    # Format anomalies for return
    result = []
    for _, row in anomalies.iterrows():
        # Skip anomalies from more than 7 days ago
        if (datetime.now().date() - row["date"]) > timedelta(days=7):
            continue
            
        anomaly_type = "unusually_high_aov" if row["z_score"] > 0 else "unusually_low_aov"
        
        # Calculate percentage difference from expected
        pct_diff = (row["aov"] - row["mean"]) / row["mean"] if row["mean"] > 0 else 0
        
        # Determine severity (1-5)
        severity = min(5, max(1, int(abs(row["z_score"]))))
        
        anomaly = {
            "type": anomaly_type,
            "date": row["date"].strftime("%Y-%m-%d"),
            "value": float(row["aov"]),
            "expected_value": float(row["mean"]),
            "z_score": float(row["z_score"]),
            "percentage_change": float(pct_diff),
            "severity": severity,
            "title": f"{'High' if row['z_score'] > 0 else 'Low'} Average Order Value Anomaly",
            "description": f"Average order value on {row['date'].strftime('%Y-%m-%d')} was {abs(pct_diff)*100:.1f}% {'higher' if pct_diff > 0 else 'lower'} than expected (${row['aov']:.2f} vs ${row['mean']:.2f}).",
            "metrics": {
                "actual_aov": float(row["aov"]),
                "expected_aov": float(row["mean"]),
                "z_score": float(row["z_score"]),
                "percentage_difference": float(pct_diff),
                "order_count": int(row["order_count"]),
            }
        }
        result.append(anomaly)
    
    return result


async def generate_anomaly_alerts(db: AsyncSession, store_id: str) -> List[Dict[str, Any]]:
    """
    Generate alert messages for detected anomalies.
    
    Args:
        db: Database session
        store_id: Store ID
    
    Returns:
        list: List of alert messages
    """
    # Get unsent anomaly insights
    insights = await crud.get_unsent_insights(db, store_id)
    
    # Filter to anomalies only
    anomaly_insights = [insight for insight in insights if insight.is_anomaly]
    
    if not anomaly_insights:
        return []
    
    # Get store info
    store = await crud.get_store(db, store_id)
    if not store:
        logger.error(f"Store not found: {store_id}")
        return []
    
    # Generate alert messages
    alerts = []
    for insight in anomaly_insights:
        try:
            # Use AI agent to generate a natural language alert
            alert_message = await sales_analyst_agent.generate_anomaly_alert(
                anomaly_data=insight.metrics,
                store_name=store.name
            )
            
            # Mark the insight as sent
            await crud.mark_insight_as_sent(db, str(insight.id))
            
            alerts.append({
                "insight_id": str(insight.id),
                "title": insight.title,
                "message": alert_message,
                "severity": insight.severity,
                "created_at": insight.created_at.isoformat()
            })
        except Exception as e:
            logger.error(f"Error generating anomaly alert: {e}")
    
    return alerts