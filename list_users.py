import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import User

async def list_all_users():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.id, User.email, User.full_name))
        users = result.all()
        
        print("All registered users:")
        print("-" * 60)
        for user in users:
            print(f"ID: {user.id}, Email: {user.email}, Name: {user.full_name}")
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(list_all_users())