import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

async def test_mongo():
    ROOT_DIR = Path(__file__).parent
    load_dotenv(ROOT_DIR / ".env")
    
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    
    print(f"Testing connection to {mongo_url} (DB: {db_name})")
    
    try:
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        # Try to ping
        await client.admin.command('ping')
        print("MongoDB Ping successful!")
        
        # Try to list collections
        collections = await db.list_collection_names()
        print(f"Collections: {collections}")
        
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    asyncio.run(test_mongo())
