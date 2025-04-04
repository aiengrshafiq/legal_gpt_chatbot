import os
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
import config

def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        pages.append((i + 1, page.get_text()))
    return pages  # list of (page_num, text)

def create_embeddings():
    docs = []

    for file in os.listdir(config.DATA_FOLDER):
        if file.endswith('.pdf'):
            path = os.path.join(config.DATA_FOLDER, file)
            pages = extract_text(path)
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

            for page_num, page_text in pages:
                chunks = splitter.split_text(page_text)
                for chunk in chunks:
                    docs.append(Document(
                        page_content=chunk,
                        metadata={"source": file, "page": page_num}
                    ))

    # Handle empty doc case (e.g., all files deleted)
    if not docs:
        if os.path.exists(config.VECTOR_STORE_PATH):
            for f in os.listdir(config.VECTOR_STORE_PATH):
                os.remove(os.path.join(config.VECTOR_STORE_PATH, f))
        return

    embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY, model=config.EMBEDDING_MODEL)
    vectorstore = FAISS.from_documents(docs, embeddings)
    vectorstore.save_local(config.VECTOR_STORE_PATH)

def load_vectorstore():
    if not os.listdir(config.VECTOR_STORE_PATH):
        return None
    embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY, model=config.EMBEDDING_MODEL)
    vectorstore = FAISS.load_local(
        config.VECTOR_STORE_PATH,
        embeddings,
        allow_dangerous_deserialization=True
    )
    return vectorstore

def delete_pdf(filename):
    file_path = os.path.join(config.DATA_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        create_embeddings()
        return True
    return False
