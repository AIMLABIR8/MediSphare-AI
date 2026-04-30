import os
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

DATA_PATH = r"C:\Users\Abir\OneDrive\Desktop\MEDICAL_AI\data"

DB_FAISS_PATH = "backend/vectorstore/db_faiss"

def load_pdf_files(data):
    loader = DirectoryLoader(
        data,
        glob="*.pdf",
        loader_cls=PyPDFLoader
    )
    return loader.load()

def create_chunks(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    return splitter.split_documents(documents)

def main():
    print("📥 Loading PDFs...")
    documents = load_pdf_files(DATA_PATH)
    print(f"Loaded {len(documents)} pages")

    print("✂️ Creating chunks...")
    chunks = create_chunks(documents)
    print(f"Created {len(chunks)} chunks")

    print("🧠 Creating embeddings...")
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    print("💾 Saving FAISS DB...")
    db = FAISS.from_documents(chunks, embedding_model)
    db.save_local(DB_FAISS_PATH)

    print("✅ Done!")

if __name__ == "__main__":
    main()

