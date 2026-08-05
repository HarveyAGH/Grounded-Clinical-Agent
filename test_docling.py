
from pathlib import Path
from docling.document_converter import DocumentConverter

source = Path("data/PDFS/2607.28631v1.pdf")
converter = DocumentConverter()
doc = converter.convert(source).document
print(doc.save_as_markdown(filename=Path("data/PDFS/raw/research_paper.md")))


