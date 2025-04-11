# from embeddings import embed_pdf
# from ner_utils import extract_entities
# from utils import extract_text_from_text_pdf
# import os

# def test_embed_pdf():
#     test_file = "users_temp/sample_arabic_law.pdf"  # Put an Arabic PDF here
#     case_id = os.path.basename(test_file).replace(".pdf", "")
    
#     print("\n✅ Embedding PDF...")
#     docs = embed_pdf(test_file, case_id)

#     for doc in docs[:2]:  # print only first 2 for brevity
#         print("\n--- Chunk ---")
#         print(doc.page_content[:300])
#         print("Metadata:", doc.metadata)

#         print("\nExtracted Entities:")
#         print(extract_entities(doc.page_content))

from qdrant_client.http.models import VectorParams, Distance
from qdrant_client import QdrantClient
import config

import streamlit as st
import os
import utils

from datetime import datetime
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
from db import SessionLocal
from models import CaseLog
from pathlib import Path

def setup_qdrant_collections():
    print("function called setup_qdrant_collections")
    client = QdrantClient(
        host=config.QDRANT_HOST,
        port=config.QDRANT_PORT,
        https=config.QDRANT_USE_HTTPS,
        api_key=config.QDRANT_API_KEY,
    )

    collections = [
        # ("uae_law_openai", 1536),
        ("uae_law_arabert", 768)
    ]

    for name, size in collections:
        try:
            client.get_collection(name)
            print(f"[INFO] Collection '{name}' already exists.")
        except:
            client.recreate_collection(
                collection_name=name,
                vectors_config=VectorParams(size=size, distance=Distance.COSINE)
            )
            print(f"[✅] Created collection: {name} with vector size: {size}")

def delete_qdrant_collections():
    print("function called delete_qdrant_collections")
    client = QdrantClient(
        host=config.QDRANT_HOST,
        port=config.QDRANT_PORT,
        https=config.QDRANT_USE_HTTPS,
        api_key=config.QDRANT_API_KEY,
    )
    client.delete_collection(collection_name="uae_law_openai")


def test_crawler():
    from crawler.scraper import crawl_all_sites
    new_blobs = crawl_all_sites(force=False)
    for blob in new_blobs:
        utils.create_embeddings(force=False, specific_file=blob)
    print("[✅] Website crawled finished successfully")
     

if __name__ == "__main__":
    #setup_qdrant_collections()
    #delete_qdrant_collections()
    test_crawler()
