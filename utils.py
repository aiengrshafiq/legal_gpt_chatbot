import os
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores.faiss import FAISS
import config

def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ''
    for page in doc:
        text += page.get_text()
    return text

def create_embeddings():
    texts = []
    for file in os.listdir(config.DATA_FOLDER):
        if file.endswith('.pdf'):
            text = extract_text(os.path.join(config.DATA_FOLDER, file))
            texts.append(text)
    
    if not texts:
        # Avoids error if no PDFs are found
        if os.path.exists(config.VECTOR_STORE_PATH):
            for file in os.listdir(config.VECTOR_STORE_PATH):
                os.remove(os.path.join(config.VECTOR_STORE_PATH, file))
        return

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.create_documents(texts)

    embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY, model=config.EMBEDDING_MODEL)
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(config.VECTOR_STORE_PATH)

def load_vectorstore():
    if not os.listdir(config.VECTOR_STORE_PATH):
        return None  # return None if no embeddings
    embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY, model=config.EMBEDDING_MODEL)
    vectorstore = FAISS.load_local(
        config.VECTOR_STORE_PATH, 
        embeddings, 
        allow_dangerous_deserialization=True  # <-- Add this parameter
    )
    return vectorstore

def delete_pdf(filename):
    file_path = os.path.join(config.DATA_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        create_embeddings()
        return True
    return False
