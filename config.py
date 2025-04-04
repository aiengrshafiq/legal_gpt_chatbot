import os
from dotenv import load_dotenv

# Load from .env if running locally
if os.getenv("FLASK_ENV") == "development":
    load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
GPT_MODEL = "gpt-4-turbo"
TEMPERATURE = 0.0

DATA_FOLDER = "./data"
VECTOR_STORE_PATH = "./embeddings/faiss_index"
