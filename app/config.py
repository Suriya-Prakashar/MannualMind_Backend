import os
from dotenv import load_dotenv

load_dotenv()


MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "manualmind")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "documents")


if not MONGODB_URI:
    raise ValueError("MONGODB_URI is not set in the .env file")