import streamlit as st
import os
import utils
import config
from datetime import datetime
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain_community.chat_models import ChatOpenAI

from pathlib import Path
from fpdf import FPDF

os.makedirs("case_reports", exist_ok=True)


st.set_page_config(page_title="Legal GPT Assistant", layout="wide")
os.makedirs("users_temp", exist_ok=True)
os.makedirs("case_logs", exist_ok=True)

# === Authentication ===
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

# === Sidebar PDF Management ===
st.sidebar.title("📁 Law Document Manager")
uploaded_file = st.sidebar.file_uploader("Upload UAE Law PDF", type=["pdf"])
if uploaded_file:
    file_path = os.path.join(config.DATA_FOLDER, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.sidebar.success(f"{uploaded_file.name} uploaded!")
    utils.create_embeddings()

st.sidebar.subheader("Existing Law PDFs:")
pdf_files = [f for f in os.listdir(config.DATA_FOLDER) if f.endswith('.pdf')]
for pdf in pdf_files:
    col1, col2 = st.sidebar.columns([0.75, 0.25])
    col1.markdown(f"📄 `{pdf}`")
    if col2.button("🗑️", key=pdf):
        utils.delete_pdf(pdf)
        st.sidebar.success(f"{pdf} deleted!")
        st.rerun()

if st.sidebar.button("🔄 Rebuild Embeddings"):
    utils.create_embeddings()
    st.sidebar.success("Embeddings rebuilt successfully.")

# === LLM Utility Functions ===
def load_llm(temp=0.0):
    return ChatOpenAI(api_key=config.OPENAI_API_KEY, model=config.GPT_MODEL, temperature=temp)

def setup_qa_chain(temp=0.0, k=6):
    vectorstore = utils.load_vectorstore()
    if not vectorstore:
        return None, None
    llm = load_llm(temp)
    prompt_template = """You are a legal assistant. Use the context below to answer the user's question.
If the answer is not present, reply:
"Sorry, the information you're asking for isn't available in the provided documents."

Context:
{context}

Question:
{question}

Answer:"""
    PROMPT = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
    qa_chain = RetrievalQA.from_chain_type(
        llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": k}),
        chain_type_kwargs={"prompt": PROMPT},
        return_source_documents=True
    )
    return qa_chain, vectorstore


# === UI Tabs ===
tab1, tab2, tab3 = st.tabs(["💬 Ask a Legal Question", "📄 Upload Legal Case", "🛠️ Admin Dashboard"])


# === Tab 1: Text-Based Q&A ===
with tab1:
    st.title("💬 Ask a Legal Question")
    if "history" not in st.session_state:
        st.session_state["history"] = []

    query = st.text_input("Type your legal question:")

    if st.button("Submit Question"):
        with st.spinner("Retrieving answer..."):
            qa_chain, _ = setup_qa_chain(temp=0.0, k=6)
            if qa_chain is None:
                st.error("No law documents available. Please upload at least one PDF.")
            else:
                response = qa_chain({"query": query})
                answer = response["result"]

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
        st.divider()

# === Tab 2: Upload Case PDF ===
with tab2:
    st.title("📄 Upload a Legal Case Document")
    case_pdf = st.file_uploader("Upload case document", type=["pdf"], key="case_upload")
    if st.button("Get Legal Advice"):
        if not case_pdf:
            st.warning("Please upload a legal case PDF.")
        else:
            temp_path = os.path.join("users_temp", case_pdf.name)
            with open(temp_path, "wb") as f:
                f.write(case_pdf.getbuffer())

            try:
                pages = utils.extract_text(temp_path)
                if not pages:
                    st.error("Unable to extract text. The PDF might be empty or scanned as image.")
                    st.stop()
            except Exception as e:
                st.error(f"Error reading PDF: {e}")
                st.stop()

            case_text = "\n".join([text for _, text in pages])
            st.markdown("#### 📝 Case Preview")
            st.markdown(case_text[:3000])

            with st.spinner("Analyzing case and generating advice..."):
                qa_chain, _ = setup_qa_chain(temp=0.5, k=10)
                if qa_chain is None:
                    st.error("No law documents found. Please upload them in the sidebar.")
                else:
                    response = qa_chain({"query": case_text})
                    advice = response["result"]

                    # Log to file
                    log_file = os.path.join("case_logs", f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
                    with open(log_file, "w", encoding="utf-8") as log:
                        log.write(f"=== Legal Case Text ===\n{case_text}\n\n=== Legal Advice ===\n{advice}")

                    st.markdown("### 📾 Legal Advice:")
                    st.markdown(advice)

                    if "Sorry, the information you're asking for isn't available" not in advice:
                        with st.expander("📖 View Sources"):
                            for i, doc in enumerate(response["source_documents"], 1):
                                meta = doc.metadata or {}
                                filename = meta.get("source", "Unknown file")
                                page = meta.get("page", "Unknown page")
                                excerpt = doc.page_content.strip().replace("\n", " ")[:300]
                                st.markdown(f"**File:** `{filename}` | **Page:** `{page}`\n\n```text\n{excerpt}...\n```")


#--- Tab 3 - Admin Dashboard----#
with tab3:
    st.title("🛠️ Admin Dashboard")
    st.subheader("📋 Case History")

    logs = sorted(Path("case_logs").glob("*.txt"), reverse=True)
    if not logs:
        st.info("No case logs available.")
        st.stop()

    search_term = st.text_input("🔍 Search by keyword, date, or file name:")

    for log_file in logs:
        log_name = log_file.name
        date_str = log_name.replace(".txt", "").replace("_", " ")
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()

        if search_term.lower() not in content.lower():
            continue

        with st.expander(f"📄 Case: {log_name}"):
            st.markdown(f"**🕒 Date:** {date_str}")
            if "=== Legal Case Text ===" in content:
                case_part = content.split("=== Legal Case Text ===")[1].split("=== Legal Advice ===")[0].strip()
                advice_part = content.split("=== Legal Advice ===")[1].strip()
                st.markdown("**📝 Case Content:**")
                st.code(case_part[:2000] + ("..." if len(case_part) > 2000 else ""))
                st.markdown("**📾 Legal Advice:**")
                st.success(advice_part)

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(f"📥 Download PDF", key="download_"+log_name):
                    output_pdf_path = f"case_reports/{log_name.replace('.txt', '.pdf')}"
                    utils.generate_pdf_advice(log_file, output_pdf_path)
                    with open(output_pdf_path, "rb") as pdf_file:
                        st.download_button(
                            label="Download Advice as PDF",
                            data=pdf_file,
                            file_name=os.path.basename(output_pdf_path),
                            mime="application/pdf",
                        )

            with col2:
                if st.button(f"🗑 Delete", key="delete_"+log_name):
                    os.remove(log_file)
                    st.warning(f"Deleted {log_name}")
                    st.rerun()

