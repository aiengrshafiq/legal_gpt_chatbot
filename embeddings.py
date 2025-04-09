from utils import extract_text_from_text_pdf, extract_text_from_scanned_pdf, detect_language
from arabic_embedder import get_arabic_embedding
from openai_embedder import get_openai_embedding
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader
import os

def embed_pdf(local_path, local_name, llm=None):
    if llm is None:
        from langchain.chat_models import ChatOpenAI
        import config
        llm = ChatOpenAI(api_key=config.OPENAI_API_KEY, model=config.GPT_MODEL)

    docs = []

    # Try to extract text from PDF (OCR fallback)
    text = extract_text_from_text_pdf(local_path)
    if len(text.strip()) < 100:
        # OCR for scanned PDFs
        text = extract_text_from_scanned_pdf(local_path, lang="ara")

    lang = detect_language(text)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(text)

    for i, chunk in enumerate(chunks):
        try:
            tag_prompt = f"Assign 2-4 short relevant legal topic tags (comma-separated) for the following law excerpt:\n\n{chunk[:1000]}"
            tags_response = llm.invoke(tag_prompt)
            tags = [t.strip() for t in tags_response.split(",")]
        except Exception as e:
            print(f"Tagging failed: {e}")
            tags = []

        embedding = get_arabic_embedding(chunk) if lang == "ar" else get_openai_embedding(chunk)

        docs.append(Document(
            page_content=chunk,
            metadata={
                "source": local_name,
                "lang": lang,
                "chunk_id": f"{local_name}_{i}",
                "tags": tags
            }
        ))

    return docs
