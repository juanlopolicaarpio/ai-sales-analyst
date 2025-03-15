import sys
import os
from pathlib import Path

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Print the content of the database file to see what's going on
print("Checking database.py file...")
with open('app/db/database.py', 'r') as f:
    content = f.read()
    print(content)

print("\nTrying to import modules...")
from app.db.database import engine, AsyncSessionLocal, get_async_db

print("Available objects in database module:", dir(sys.modules['app.db.database']))