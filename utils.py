import os
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from langchain_community.chat_models import ChatOpenAI
import config

def extract_text(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                pages.append((i + 1, text))
        return pages
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return []

def create_embeddings():
    docs = []
    llm = ChatOpenAI(api_key=config.OPENAI_API_KEY, model=config.GPT_MODEL)

    for file in os.listdir(config.DATA_FOLDER):
        if file.endswith('.pdf'):
            path = os.path.join(config.DATA_FOLDER, file)
            pages = extract_text(path)
            if not pages:
                print(f"Skipping empty or unreadable PDF: {file}")
                continue

            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            for page_num, page_text in pages:
                chunks = splitter.split_text(page_text)
                for chunk in chunks:
                    try:
                        tag_prompt = f"Assign 2-4 short relevant legal topic tags (comma-separated) for the following law excerpt:\n\n{chunk[:1000]}"
                        tags_response = llm.invoke(tag_prompt)
                        tags = [t.strip() for t in tags_response.split(",")]
                    except Exception as e:
                        print(f"Tagging failed: {e}")
                        tags = []

                    docs.append(Document(
                        page_content=chunk,
                        metadata={"source": file, "page": page_num, "tags": tags}
                    ))

    if not docs:
        if os.path.exists(config.VECTOR_STORE_PATH):
            for f in os.listdir(config.VECTOR_STORE_PATH):
                os.remove(os.path.join(config.VECTOR_STORE_PATH, f))
        return

    embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY, model=config.EMBEDDING_MODEL)
    vectorstore = FAISS.from_documents(docs, embeddings)
    vectorstore.save_local(config.VECTOR_STORE_PATH)

def load_vectorstore():
    if not os.path.isdir(config.VECTOR_STORE_PATH) or not os.listdir(config.VECTOR_STORE_PATH):
        return None
    embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY, model=config.EMBEDDING_MODEL)
    return FAISS.load_local(config.VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)

def delete_pdf(filename):
    file_path = os.path.join(config.DATA_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        create_embeddings()
        return True
    return False
