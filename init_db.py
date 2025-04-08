import os
from dotenv import load_dotenv
load_dotenv()

from db import Base, engine
from models import CaseLog

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("✅ PostgreSQL tables created.")
