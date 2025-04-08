import streamlit as st
import os
import utils
import config
from datetime import datetime
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
from db import SessionLocal
from models import CaseLog
from pathlib import Path

st.set_page_config(page_title="Legal GPT Assistant", layout="wide")
os.makedirs("users_temp", exist_ok=True)
os.makedirs("case_reports", exist_ok=True)

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
            st.rerun()
        else:
            st.error("Invalid username or password")
    st.stop()

# === Sidebar PDF Management ===
st.sidebar.title("📁 Law Document Manager (Cloud)")

uploaded_file = st.sidebar.file_uploader("Upload UAE Law PDF", type=["pdf"])
if uploaded_file:
    filename = utils.upload_pdf(uploaded_file, uploaded_file.name)
    st.sidebar.success(f"{filename} uploaded to cloud.")
    utils.create_embeddings()

st.sidebar.subheader("📂 Stored PDFs in Azure Blob:")
pdf_files = [f for f in utils.list_files() if f.endswith(".pdf") and f.startswith("legal-files/")]
for pdf in pdf_files:
    col1, col2 = st.sidebar.columns([0.75, 0.25])
    col1.markdown(f"📄 `{os.path.basename(pdf)}`")
    if col2.button("🗑️", key=pdf):
        utils.delete_pdf(pdf)
        st.sidebar.success(f"{pdf} deleted from cloud.")
        st.rerun()

if st.sidebar.button("🔄 Rebuild Embeddings"):
    utils.create_embeddings(force=False)
    st.sidebar.success("Embeddings rebuilt successfully from cloud PDFs.")

# === LLM Setup ===
def load_llm(temp=0.0):
    return ChatOpenAI(api_key=config.OPENAI_API_KEY, model=config.GPT_MODEL, temperature=temp)

def setup_qa_chain(temp=0.0, k=6):
    retriever = utils.load_vectorstore(k=k)  # ✅ this is now the retriever
    if not retriever:
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
        retriever=retriever,  # ✅ now works
        chain_type_kwargs={"prompt": PROMPT},
        return_source_documents=True
    )

    return qa_chain, retriever


# === UI Tabs ===
tab1, tab2, tab3 = st.tabs(["💬 Ask a Legal Question", "📄 Upload Legal Case", "🛠️ Admin Dashboard"])

# === Tab 1 ===
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
                response = qa_chain.invoke({"query": query})
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

# === Tab 2 ===
with tab2:
    st.title("📄 Upload a Legal Case Document")
    case_pdf = st.file_uploader("Upload case document", type=["pdf"], key="case_upload")
    if st.button("Get Legal Advice"):
        if not case_pdf:
            st.warning("Please upload a legal case PDF.")
        else:
            # temp_path = os.path.join("users_temp", case_pdf.name)
            # with open(temp_path, "wb") as f:
            #     f.write(case_pdf.getbuffer())
            filename = utils.upload_pdf(case_pdf, case_pdf.name, is_case=True)
            temp_path = os.path.join("temp_pdfs", filename)

            try:
                pages = utils.extract_text(temp_path)
                if not pages:
                    st.error("Unable to extract text. The PDF might be empty or scanned.")
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
                    st.error("No law documents found.")
                else:
                    #response = qa_chain({"query": case_text})
                    response = qa_chain.invoke({"query": case_text})
                    advice = response["result"]

                    db = SessionLocal()
                    new_case = CaseLog(
                        case_title=case_pdf.name,
                        case_text=case_text,
                        advice=advice
                    )
                    db.add(new_case)
                    db.commit()
                    db.refresh(new_case)
                    st.success(f"Saved to DB as Case ID: {new_case.id}")

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

# === Tab 3 ===
with tab3:
    st.title("🛠️ Admin Dashboard")
    st.subheader("📋 Case History")
    st.subheader("🕷️ Crawl UAE Legal Sites")

    if st.button("🔁 Start Full Crawl"):
        with st.spinner("Crawling sites, downloading PDFs, saving to Azure..."):
            from crawler.scraper import crawl_all_sites
            utils.create_embeddings(force=False)
            st.success("Crawling and embedding complete.")

    db = SessionLocal()
    search_term = st.text_input("🔍 Search cases by keyword:")
    query = db.query(CaseLog)
    if search_term:
        query = query.filter(CaseLog.case_text.ilike(f"%{search_term}%"))

    for case in query.order_by(CaseLog.created_at.desc()).all():
        with st.expander(f"📄 Case: {case.case_title} (ID: {case.id})"):
            st.markdown(f"**🕒 Date:** {case.created_at.strftime('%Y-%m-%d %H:%M')}")
            st.markdown("**📝 Case Content:**")
            st.code(case.case_text[:2000] + ("..." if len(case.case_text) > 2000 else ""))
            st.markdown("**📾 Legal Advice:**")
            st.success(case.advice)

        col1, col2 = st.columns([0.3, 0.7])
        with col1:
            if st.button(f"📥 Download Advice as PDF", key=f"pdf_{case.id}"):
                output_path = f"case_reports/case_{case.id}.pdf"
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(f"=== Legal Case Text ===\n{case.case_text}\n\n=== Legal Advice ===\n{case.advice}")
                utils.generate_pdf_advice(output_path, output_path)
                with open(output_path, "rb") as pdf_file:
                    st.download_button(
                        label="⬇️ Download PDF",
                        data=pdf_file,
                        file_name=os.path.basename(output_path),
                        mime="application/pdf",
                    )

