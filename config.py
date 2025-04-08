import os
from dotenv import load_dotenv
FLASK_ENV = os.getenv("FLASK_ENV", "development")
# Load from .env if running locally
if FLASK_ENV == "development":
    load_dotenv()


print("DEBUG: FLASK_ENV =", FLASK_ENV)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("ERROR: OPENAI_API_KEY not found. Make sure it's set in the environment variables.")

EMBEDDING_MODEL = "text-embedding-3-small"
GPT_MODEL = "gpt-4-turbo"
TEMPERATURE = 0.0

DATA_FOLDER = "./data"
VECTOR_STORE_PATH = "./embeddings/faiss_index"

QDRANT_HOST = os.getenv("QDRANT_HOST","6ef14677-369c-4c22-91f6-413cdc7d7c93.europe-west3-0.gcp.cloud.qdrant.io")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 443))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_USE_HTTPS = os.getenv("QDRANT_USE_HTTPS", "true").lower() == "true"

