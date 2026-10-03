import os

from dotenv import load_dotenv


load_dotenv()


MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv(
    "MONGODB_DATABASE",
    "manualmind",
)
MONGODB_COLLECTION = os.getenv(
    "MONGODB_COLLECTION",
    "documents",
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


if not MONGODB_URI:
    raise ValueError(
        "MONGODB_URI is not set in the .env file"
    )


if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is not set in the .env file"
    )