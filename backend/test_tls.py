import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('.env')
mongo_url = os.environ.get('MONGO_URL')

async def test():
    client = AsyncIOMotorClient(mongo_url, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
    try:
        res = await client.admin.command('ping')
        print("Success:", res)
    except Exception as e:
        print("Error:", e)
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test())
