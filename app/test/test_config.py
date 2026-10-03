from app.config import (
    MONGODB_URI,
    MONGODB_DATABASE,
    MONGODB_COLLECTION,
    GEMINI_API_KEY,
)


def main():
    print("Configuration test")
    print("-------------------")

    print("MongoDB URI loaded:", bool(MONGODB_URI))
    print("MongoDB Database:", MONGODB_DATABASE)
    print("MongoDB Collection:", MONGODB_COLLECTION)

    print("Gemini API key loaded:", bool(GEMINI_API_KEY))

    if not MONGODB_URI:
        print("ERROR: MONGODB_URI is missing")
        return

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY is missing")
        return

    print("\nAll configuration values loaded successfully.")


if __name__ == "__main__":
    main()