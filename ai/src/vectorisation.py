"""
vectorisation.py

Chunks cleaned PDF text, embeds it, and stores it in a persistent
ChromaDB collection for later retrieval by chatbot.py / fetch_papers.py.

Fixes vs. the original script:
  - text_splitter.split_text() used instead of create_documents() + str(),
    which was previously embedding the Document's repr (page_content=...
    metadata={}) instead of the actual chunk text.
  - "pdf_id" is now derived from the filename instead of the undefined/
    shadowed builtin `id`.
  - Embeddings are stored in Chroma (with metadata) instead of a flat
    pickle, so they're actually queryable (similarity search, filtering)
    rather than just sitting on disk as a DataFrame.
"""

import os
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pdf_to_text import extract_cleaned_text

# --- config ---------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_PATH = os.path.join(BASE_DIR, "data", "chroma_db")
COLLECTION_NAME = "papers"
EMBEDDING_MODEL_NAME = "multi-qa-MiniLM-L6-cos-v1"

# --- setup ------------------------------------------------------------------

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL_NAME
)

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_fn,
    metadata={"hnsw:space": "cosine"},
)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    length_function=len,
)


# --- core functions -----------------------------------------------------

def vectorising_pdf(pdf_path: str, extra_metadata: dict | None = None) -> int:
    """
    Extract, chunk, embed, and upsert a single PDF into the Chroma collection.
    Returns the number of chunks stored.

    extra_metadata: optional dict of extra fields to attach to every chunk
    of this PDF (e.g. methodology tags pulled from your KG pipeline).
    """
    pdf_id = os.path.splitext(os.path.basename(pdf_path))[0]

    text = extract_cleaned_text(pdf_path)
    if not text or not text.strip():
        print(f"[skip] No text extracted from {pdf_path}")
        return 0

    chunks = text_splitter.split_text(text)
    if not chunks:
        print(f"[skip] No chunks produced for {pdf_path}")
        return 0

    ids = [f"{pdf_id}_{i}" for i in range(len(chunks))]
    metadatas = []
    for i in range(len(chunks)):
        meta = {"pdf_id": pdf_id, "chunk_index": i, "source_path": pdf_path}
        if extra_metadata:
            meta.update(extra_metadata)
        metadatas.append(meta)

    # upsert = safe to re-run on the same PDF without creating duplicates
    collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)

    print(f"[ok] Stored {len(chunks)} chunks for '{pdf_id}'")
    return len(chunks)


def vectorising_folder(folder_path: str) -> None:
    """Process every PDF in a folder."""
    pdfs = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    if not pdfs:
        print(f"No PDFs found in {folder_path}")
        return

    total = 0
    for fname in pdfs:
        total += vectorising_pdf(os.path.join(folder_path, fname))
    print(f"\nDone. {total} chunks stored across {len(pdfs)} PDFs.")


if __name__ == "__main__":
    data_dir = os.path.join(BASE_DIR, "data/example_pdfs")
    vectorising_folder(data_dir)

    #vectorising_pdf(r"E:\Codes\c2c_name_tbd_backend\ai\src\data\example.pdf")
    # sanity check
    print("\nCollection count:", collection.count())