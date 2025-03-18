#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import get_async_db
from app.services.analytics import get_sales_data


async def test_sales_data():
    """Test async database operations with get_sales_data."""
    print("Testing get_sales_data function...")
    
    async for db in get_async_db():
        try:
            # Use known values
            store_id = "2834d598-c7d7-4444-aaa3-4c4458c3d92b"  # Your test store ID
            time_range = "yesterday"
            timezone = "UTC"
            
            print(f"Calling get_sales_data with store_id={store_id}, time_range={time_range}")
            result = await get_sales_data(db, store_id, time_range, timezone)
            print("Success! Function returned:", result is not None)
            return True
        except Exception as e:
            print(f"Error testing get_sales_data: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    asyncio.run(test_sales_data())