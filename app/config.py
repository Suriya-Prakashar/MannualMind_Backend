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
GEMINI_GENERATION_MODEL = os.getenv(
    "GEMINI_GENERATION_MODEL",
    "gemini-3.5-flash",
)

# Hybrid Search & Reranking configuration
SEMANTIC_CANDIDATE_LIMIT = int(
    os.getenv("SEMANTIC_CANDIDATE_LIMIT", "20")
)
KEYWORD_CANDIDATE_LIMIT = int(
    os.getenv("KEYWORD_CANDIDATE_LIMIT", "20")
)
RRF_K = int(
    os.getenv("RRF_K", "60")
)
RERANKING_ENABLED = (
    os.getenv("RERANKING_ENABLED", "true").lower()
    in ("true", "1", "yes")
)
RERANK_CANDIDATE_LIMIT = int(
    os.getenv("RERANK_CANDIDATE_LIMIT", "10")
)
RETRIEVAL_TOP_K = int(
    os.getenv("RETRIEVAL_TOP_K", "5")
)

# Maintenance Email & SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv(
    "SMTP_FROM_EMAIL",
    "maintenance@manualmind.ai",
)
SMTP_USE_TLS = (
    os.getenv("SMTP_USE_TLS", "true").lower()
    in ("true", "1", "yes")
)
SMTP_TIMEOUT_SECONDS = int(
    os.getenv("SMTP_TIMEOUT_SECONDS", "10")
)

if not MONGODB_URI:
    raise ValueError(
        "MONGODB_URI is not set in the .env file"
    )


if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is not set in the .env file"
    )