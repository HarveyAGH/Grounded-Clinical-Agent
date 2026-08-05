"""
Ingestion entrypoint: wires parse -> chunk -> embed into one run.
Each stage stays its own testable module; this is the only place that
needs to know how they connect.
"""
from pathlib import Path

from .doc_parser import convert_pdf_raw
from .content_processor import chunk_markdown_files
from .vectorstore import build_vectorstore

PDF_DIR = Path("data/PDFS")
RAW_MD_DIR = Path("data/raw")


def run_ingestion() -> None:
    md_paths = convert_pdf_raw(pdf_dir=PDF_DIR, output_dir=RAW_MD_DIR)
    print(f"Parsed {len(md_paths)} PDF(s) into markdown.")

    chunks = chunk_markdown_files(md_paths)
    print(f"Produced {len(chunks)} chunks.")

    build_vectorstore(chunks)
    print("Ingestion complete -- vector store is ready.")


if __name__ == "__main__":
    run_ingestion()