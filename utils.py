import os
import json
import re
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain.docstore.document import Document

from langchain_qdrant import QdrantVectorStore
from langchain_core.vectorstores import VectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from langchain_openai import ChatOpenAI
from azure_blob import upload_file, download_file, delete_file, list_files
import config
from fpdf import FPDF

from pdf2image import convert_from_path
import pytesseract
from PIL import Image
from extractors import extract_text, extract_text_from_html
from bs4 import BeautifulSoup

from langdetect import detect, DetectorFactory
from pdf2image import convert_from_path
import pytesseract
from PyPDF2 import PdfReader
from PIL import Image

from openai_embedder import get_openai_embedding
from arabic_embedder import get_arabic_embedding

from qdrant_client.models import PointStruct
import uuid


EMBED_RECORD_PATH = "embedded_files.json"

TEMP_DIR = "temp_pdfs"
os.makedirs(TEMP_DIR, exist_ok=True)

QDRANT_COLLECTION_NAME = "uae_law"
DetectorFactory.seed = 0


def get_qdrant_vectorstore(embeddings, collection_name) -> VectorStore:
    client = QdrantClient(
        host=config.QDRANT_HOST,
        port=config.QDRANT_PORT,
        https=config.QDRANT_USE_HTTPS,
        api_key=config.QDRANT_API_KEY,
    )

    try:
        client.get_collection(collection_name)
    except:
        vector_size = 1536 if "openai" in collection_name else 768
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )

    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings
    )





def load_embedded_files():
    if os.path.exists(EMBED_RECORD_PATH):
        try:
            with open(EMBED_RECORD_PATH, "r") as f:
                content = f.read().strip()
                if not content:
                    return set()
                return set(json.loads(content))
        except Exception as e:
            print(f"[⚠️ JSON LOAD ERROR] {e}")
            return set()
    return set()


def save_embedded_files(files):
    with open(EMBED_RECORD_PATH, "w") as f:
        json.dump(sorted(list(files)), f)



def create_embeddings(force=False, specific_file=None):
    llm = ChatOpenAI(api_key=config.OPENAI_API_KEY, model=config.GPT_MODEL)
    from qdrant_client.models import PointStruct
    client = QdrantClient(
        host=config.QDRANT_HOST,
        port=config.QDRANT_PORT,
        https=config.QDRANT_USE_HTTPS,
        api_key=config.QDRANT_API_KEY,
    )
    embedded_files = load_embedded_files()
    processed_now = set()
    all_blobs = list_files()

    if specific_file:
        target_blobs = [specific_file]
    else:
        target_blobs = [
            f for f in all_blobs if f.endswith((".pdf", ".html"))
            and not f.startswith("case-files/")
            and (f.startswith("legal-files/") or f.startswith("crawled/pdfs/") or f.startswith("crawled/html/"))
        ]

    # Set up vectorstore (needed even if we embed per chunk)
    embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY, model=config.EMBEDDING_MODEL)

    for blob_name in target_blobs:
        local_name = os.path.basename(blob_name)
        temp_path = os.path.join(TEMP_DIR, local_name)

        if not force and local_name in embedded_files:
            print(f"[SKIP] Already embedded: {local_name}")
            continue

        try:
            download_file(blob_name, temp_path)
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

            if blob_name.endswith(".pdf"):
                pages = extract_text(temp_path)
                for page_num, page_text in pages:
                    chunks = splitter.split_text(page_text)
                    for chunk in chunks:
                        last_detected_lang = "en"
                        chunk = chunk.replace('\n', ' ').strip()
                        if not chunk or len(chunk) < 20:
                            print(f"[SKIP] Empty or short chunk: Page {page_num}")
                            continue
                        if not re.search(r'[a-zA-Z\u0600-\u06FF]', chunk):
                            print(f"[SKIP] No useful text: Page {page_num}")
                            continue

                        lang = detect_language(chunk)
                        if lang == "unknown":
                            lang = last_detected_lang
                        else:
                            last_detected_lang = lang
                        print(f"[LANG DETECTED IN PDF] {lang}: {chunk[:80]}")

                        try:
                            tag_prompt = f"Assign 2-4 short relevant legal topic tags (comma-separated) for the following law excerpt:\n\n{chunk[:1000]}"
                            tags_response = llm.invoke(tag_prompt).content
                            tags = [t.strip() for t in tags_response.split(",")]
                        except Exception as e:
                            print(f"[TAG ERROR] {e}")
                            tags = []

                        # Embed based on language
                        try:
                            collection = "uae_law_arabert" if lang == "ar" else "uae_law_openai"
                            embedding = get_arabic_embedding(chunk) if lang == "ar" else embeddings.embed_query(chunk)
                        except Exception as e:
                            print(f"[EMBED ERROR] {e}")
                            continue

                        

                        client.upsert(
                            collection_name=collection,
                            points=[
                                PointStruct(
                                    id=str(uuid.uuid4()),
                                    vector=embedding,
                                    payload={
                                        "text": chunk,
                                        "source": local_name,
                                        "page": page_num,
                                        "tags": tags,
                                        "lang": lang
                                    }
                                )
                            ]
                        )

            elif blob_name.endswith(".html"):
                html_data = extract_text_from_html(temp_path)
                for page_num, page_text, title, source_url in html_data:
                    chunks = splitter.split_text(page_text)
                    for chunk in chunks:
                        last_detected_lang = "en"
                        chunk = chunk.replace('\n', ' ').strip()
                        if not chunk or len(chunk) < 20:
                            print(f"[SKIP] Empty or short chunk: Page {page_num}")
                            continue
                        if not re.search(r'[a-zA-Z\u0600-\u06FF]', chunk):
                            print(f"[SKIP] No useful text: Page {page_num}")
                            continue

                        lang = detect_language(chunk)
                        if lang == "unknown":
                            lang = last_detected_lang
                        else:
                            last_detected_lang = lang
                        print(f"[LANG DETECTED IN HTML] {lang}: {chunk[:80]}")

                        try:
                            tag_prompt = f"Assign 2-4 short relevant legal topic tags (comma-separated) for the following law excerpt:\n\n{chunk[:1000]}"
                            tags_response = llm.invoke(tag_prompt).content
                            tags = [t.strip() for t in tags_response.split(",")]
                        except Exception as e:
                            print(f"[TAG ERROR] {e}")
                            tags = []

                        try:
                            collection = "uae_law_arabert" if lang == "ar" else "uae_law_openai"
                            embedding = get_arabic_embedding(chunk) if lang == "ar" else embeddings.embed_query(chunk)
                        except Exception as e:
                            print(f"[EMBED ERROR] {e}")
                            continue

                        

                        client.upsert(
                            collection_name=collection,
                            points=[
                                PointStruct(
                                    id=str(uuid.uuid4()),
                                    vector=embedding,
                                    payload={
                                        "text": chunk,
                                        "source": local_name,
                                        "page": page_num,
                                        "tags": tags,
                                        "lang": lang
                                    }
                                )
                            ]
                        )
            print(f"[✅] Uploaded chunk ({lang}) to Qdrant: {local_name} - Page {page_num}")
            processed_now.add(local_name)

        except Exception as e:
            print(f"[ERROR] Failed to process {blob_name}: {e}")

    if processed_now:
        print(f"[✅] Embedded documents from {len(processed_now)} new file(s).")
    else:
        print("[⚠️] No new documents embedded.")

    embedded_files.update(processed_now)
    save_embedded_files(embedded_files)
    


def load_vectorstore(lang="en", k=10):
    collection_name = "uae_law_arabert" if lang == "ar" else "uae_law_openai"
    embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY, model=config.EMBEDDING_MODEL)
    return get_qdrant_vectorstore(embeddings, collection_name).as_retriever(
        search_type="similarity",
        search_kwargs={"k": k}
    )


def delete_pdf(blob_filename):
    delete_file(blob_filename)
    return True

def upload_pdf(file_obj, filename, is_case=False):
    temp_path = os.path.join(TEMP_DIR, filename)
    with open(temp_path, "wb") as f:
        f.write(file_obj.getbuffer())
    blob_path = f"case-files/{filename}" if is_case else f"legal-files/{filename}"
    upload_file(temp_path, blob_path)
    return filename

def generate_pdf_advice(log_path, output_path):
    with open(log_path, "r", encoding="utf-8") as file:
        content = file.read()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    for line in content.split("\n"):
        pdf.multi_cell(0, 10, line)

    pdf.output(output_path)


def detect_language(text: str) -> str:
    try:
        lang = detect(text)
        if lang not in ['en', 'ar']:
            lang = 'en'
        return lang
    except:
        return "unknown"

def extract_text_from_text_pdf(file_path):
    reader = PdfReader(file_path)
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() or ""
    return full_text

def extract_text_from_scanned_pdf(file_path: str, lang: str = "eng") -> str:
    images = convert_from_path(file_path)
    extracted_text = ""
    for image in images:
        extracted_text += pytesseract.image_to_string(image, lang=lang)
    return extracted_text

def is_arabic(text: str) -> bool:
    return detect_language(text) == "ar"

def direct_qdrant_search(query, lang="en", k=10):
    client = QdrantClient(
        host=config.QDRANT_HOST,
        port=config.QDRANT_PORT,
        https=config.QDRANT_USE_HTTPS,
        api_key=config.QDRANT_API_KEY,
    )

    collection_name = "uae_law_arabert" if lang == "ar" else "uae_law_openai"
    
    if lang == "ar":
        embedding = get_arabic_embedding(query)
    else:
        embedding_model = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY, model=config.EMBEDDING_MODEL)
        embedding = embedding_model.embed_query(query)

    print(f"[DEBUG] Searching in collection: {collection_name} | Query lang: {lang}")

    search_results = client.search(
        collection_name=collection_name,
        query_vector=embedding,
        limit=k,
        with_payload=True
    )

    docs = []
    for result in search_results:
        docs.append(Document(
            page_content=result.payload['text'],
            metadata=result.payload
        ))

    return docs

