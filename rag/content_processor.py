"""
Chunking step: markdown text -> semantically-aware chunks.
v0 scope: structural (header) split + size-based split. No LLM-refined
chunking yet (deferred).
"""
from pathlib import Path
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def chunk_markdown_file(
    md_path: Path,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[Document]:
    """Splits a single markdown file into chunks: first by header, then by size."""
    if not md_path.is_file():
        raise FileNotFoundError(f"File not found: {md_path}")

    text = md_path.read_text(encoding="utf-8")

    headers_to_split_on = [("##", "main_topic")]
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on)
    header_chunks = header_splitter.split_text(text)

    # Tag every section with its source file before size-splitting -- split_documents()
    # carries existing metadata forward onto the final chunks.
    source_name = md_path.stem
    for section in header_chunks:
        section.metadata["source"] = source_name

    size_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return size_splitter.split_documents(header_chunks)


def chunk_markdown_files(
    md_paths: list[Path],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[Document]:
    """Chunks a batch of markdown files -- the actual shape convert_pdf_raw /
    convert_docx_raw / convert_TXT_raw return -- and aggregates into one list."""
    all_chunks: list[Document] = []
    for md_path in md_paths:
        all_chunks.extend(chunk_markdown_file(md_path, chunk_size, chunk_overlap))
    return all_chunks


if __name__ == "__main__":
    from .doc_parser import convert_pdf_raw

    md_paths = convert_pdf_raw(
        pdf_dir=Path("data/PDFS"),
        output_dir=Path("data/raw"),
    )
    chunks = chunk_markdown_files(md_paths)
    print(f"Produced {len(chunks)} chunks from {len(md_paths)} files.")
    if chunks:
        print("--- sample chunk ---")
        print(chunks[0].metadata)
        print(chunks[0].page_content[:300])