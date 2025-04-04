import streamlit as st
import os
import utils
import config
#from langchain.chat_models import ChatOpenAI
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA

st.set_page_config(page_title="Legal GPT Chatbot", layout="wide")

# Authentication
def authenticate(username, password):
    return username == "admin" and password == "Meta@321"

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 Login Required")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if authenticate(username, password):
            st.session_state['logged_in'] = True
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid username or password")
    st.stop()

# Sidebar for PDF Management
st.sidebar.title("📁 Manage PDFs")
uploaded_file = st.sidebar.file_uploader("Upload PDF", type=['pdf'])

if uploaded_file:
    file_path = os.path.join(config.DATA_FOLDER, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    utils.create_embeddings()
    st.sidebar.success(f"{uploaded_file.name} uploaded!")

st.sidebar.subheader("Existing PDFs:")
pdf_files = [f for f in os.listdir(config.DATA_FOLDER) if f.endswith('.pdf')]
for pdf in pdf_files:
    col1, col2 = st.sidebar.columns([0.7, 0.3])
    col1.write(pdf)
    if col2.button("🗑️", key=pdf):
        utils.delete_pdf(pdf)
        st.sidebar.success(f"{pdf} deleted!")
        st.rerun()

if st.sidebar.button("🔄 Refresh Embeddings"):
    utils.create_embeddings()
    st.sidebar.success("Embeddings updated!")

# Main Chat UI
st.title("⚖️ Legal Department GPT Assistant")

if "history" not in st.session_state:
    st.session_state["history"] = []

query = st.text_input("Ask a legal question based on uploaded PDFs:")

if st.button("Submit Question") and query:
    with st.spinner('Fetching answer...'):
        vectorstore = utils.load_vectorstore()

        if vectorstore is None:
            st.error("No documents available. Please upload at least one PDF to continue.")
        else:
            llm = ChatOpenAI(api_key=config.OPENAI_API_KEY, model=config.GPT_MODEL, temperature=config.TEMPERATURE)
            
            # Custom Prompt to restrict answers
            from langchain.prompts import PromptTemplate

            prompt_template = """You are a legal assistant. Use the context below to answer the user's question.
            If the answer is clearly not present in the context, reply with:
            "Sorry, the information you're asking for isn't available in the provided documents."

            Context:
            {context}

            Question:
            {question}

            Answer:"""

            PROMPT = PromptTemplate(
                template=prompt_template, input_variables=["context", "question"]
            )

            qa_chain = RetrievalQA.from_chain_type(
                llm,
                chain_type="stuff",
                retriever=vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 6}),
                chain_type_kwargs={"prompt": PROMPT},
                return_source_documents=True
            )

            response = qa_chain({"query": query})

            answer = response["result"]
            #sources = [doc.page_content[:200] + "..." for doc in response["source_documents"]]
            sources = []
            for doc in response["source_documents"]:
                metadata = doc.metadata or {}
                filename = metadata.get("source", "Unknown file")
                page = metadata.get("page", "Unknown page")
                text_excerpt = doc.page_content.strip().replace("\n", " ")[:300]
                sources.append(f"**File:** `{filename}` | **Page:** `{page}`\n\n```text\n{text_excerpt}...\n```")

            st.session_state.history.insert(0, (query, answer, sources))

for q, a, src in st.session_state.history:
    st.markdown(f"**Question:** {q}")
    st.markdown(f"**Answer:** {a}")
    
    if "Sorry, the information you're asking for isn't available" not in a:
        with st.expander("📖 View Sources"):
            for i, s in enumerate(src, 1):
                st.markdown(f"**Source {i}:**")
                st.markdown(s)
                st.markdown("---")
    
    st.divider()
