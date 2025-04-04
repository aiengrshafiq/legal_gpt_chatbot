import streamlit as st
import os
import utils
import config
from langchain.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA

st.set_page_config(page_title="Legal GPT Chatbot", layout="wide")

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
        st.experimental_rerun()

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
        llm = ChatOpenAI(api_key=config.OPENAI_API_KEY, model=config.GPT_MODEL, temperature=config.TEMPERATURE)

        qa_chain = RetrievalQA.from_chain_type(llm, retriever=vectorstore.as_retriever(), return_source_documents=True)
        response = qa_chain({"query": query})

        answer = response["result"]
        sources = [doc.page_content[:200] + "..." for doc in response["source_documents"]]

        st.session_state.history.insert(0, (query, answer, sources))

for q, a, src in st.session_state.history:
    st.markdown(f"**Question:** {q}")
    st.markdown(f"**Answer:** {a}")
    with st.expander("View Sources"):
        for s in src:
            st.write(s)
    st.divider()
