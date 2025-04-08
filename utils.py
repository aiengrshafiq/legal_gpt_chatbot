import os
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
from embeddings import embed_pdf
from extractors import extract_text, extract_text_from_html
from bs4 import BeautifulSoup


EMBED_RECORD_PATH = "embedded_files.json"

TEMP_DIR = "temp_pdfs"
os.makedirs(TEMP_DIR, exist_ok=True)

QDRANT_COLLECTION_NAME = "uae_law"


def get_qdrant_vectorstore(embeddings) -> VectorStore:
    client = QdrantClient(
        host=config.QDRANT_HOST,
        port=config.QDRANT_PORT,
        https=config.QDRANT_USE_HTTPS,
        api_key=config.QDRANT_API_KEY,
    )

    try:
        client.get_collection(QDRANT_COLLECTION_NAME)
    except:
        client.recreate_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )

    return QdrantVectorStore(
        client=client,
        collection_name=QDRANT_COLLECTION_NAME,
        embedding=embeddings
    )




def load_embedded_files():
    if os.path.exists(EMBED_RECORD_PATH):
        with open(EMBED_RECORD_PATH, "r") as f:
            return set(json.load(f))
    return set()

def save_embedded_files(files):
    with open(EMBED_RECORD_PATH, "w") as f:
        json.dump(sorted(list(files)), f)



def create_embeddings(force=False):
    docs = []
    llm = ChatOpenAI(api_key=config.OPENAI_API_KEY, model=config.GPT_MODEL)
    embedded_files = load_embedded_files()
    processed_now = set()

    all_blobs = list_files()

    # target_blobs = [
    #     f for f in all_blobs if (
    #         f.startswith("legal-files/") or f.startswith("crawled/pdfs/") or f.startswith("crawled/html/")
    #     ) and (f.endswith(".pdf") or f.endswith(".html"))
    # ]

    target_blobs = [
        f for f in all_blobs if f.endswith((".pdf", ".html"))
        and not f.startswith("case-files/")
        and (f.startswith("legal-files/") or f.startswith("crawled/pdfs/") or f.startswith("crawled/html/"))
    ]

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
                        try:
                            tag_prompt = f"Assign 2-4 short relevant legal topic tags (comma-separated) for the following law excerpt:\n\n{chunk[:1000]}"
                            tags_response = llm.invoke(tag_prompt).content
                            tags = [t.strip() for t in tags_response.split(",")]
                        except Exception as e:
                            print(f"[TAG ERROR] {e}")
                            tags = []

                        docs.append(Document(
                            page_content=chunk,
                            metadata={
                                "source": local_name,
                                "page": page_num,
                                "tags": tags
                            }
                        ))

            elif blob_name.endswith(".html"):
                html_data = extract_text_from_html(temp_path)
                for page_num, page_text, title, source_url in html_data:
                    chunks = splitter.split_text(page_text)
                    for chunk in chunks:
                        try:
                            tag_prompt = f"Assign 2-4 short relevant legal topic tags (comma-separated) for the following law excerpt:\n\n{chunk[:1000]}"
                            tags_response = llm.invoke(tag_prompt).content
                            tags = [t.strip() for t in tags_response.split(",")]
                        except Exception as e:
                            print(f"[TAG ERROR] {e}")
                            tags = []

                        docs.append(Document(
                            page_content=chunk,
                            metadata={
                                "source": local_name,
                                "title": title,
                                "url": source_url,
                                "page": page_num,
                                "tags": tags
                            }
                        ))

            processed_now.add(local_name)

        except Exception as e:
            print(f"[ERROR] Failed to process {blob_name}: {e}")

    if docs:
        embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY, model=config.EMBEDDING_MODEL)
        vectorstore = get_qdrant_vectorstore(embeddings)
        vectorstore.add_documents(docs, embedding=embeddings)
        print(f"[✅] Embedded {len(docs)} chunks.")
    else:
        print("[⚠️] No new documents embedded.")

    embedded_files.update(processed_now)
    save_embedded_files(embedded_files)




    


def load_vectorstore(k=6):
    embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY, model=config.EMBEDDING_MODEL)
    vectorstore = get_qdrant_vectorstore(embeddings)
    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": k})


def delete_pdf(blob_filename):
    delete_file(blob_filename)
    #create_embeddings(force=False)
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
