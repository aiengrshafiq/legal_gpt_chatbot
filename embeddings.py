# embeddings.py
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
import config
from extractors import extract_text

def embed_pdf(local_path, local_name, llm=None):
    if llm is None:
        llm = ChatOpenAI(api_key=config.OPENAI_API_KEY, model=config.GPT_MODEL)

    docs = []
    pages = extract_text(local_path)
    if not pages:
        print(f"Skipping empty/unreadable PDF: {local_path}")
        return []

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
                metadata={"source": local_name, "page": page_num, "tags": tags}
            ))
    return docs
