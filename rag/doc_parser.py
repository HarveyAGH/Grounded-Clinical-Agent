"""
Parsing step: PDF -> markdown text on disk.
v0 scope: plain text extraction only. No table/image handling yet (deferred).
"""
from pathlib import Path
from docling.document_converter import DocumentConverter



def convert_pdf_raw(pdf_dir: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_paths:
        raise FileNotFoundError(f"PDF not found in: {pdf_dir}")
    results = []
    convert = DocumentConverter()
    for res in convert.convert_all(pdf_paths, raises_on_error=False):
        if res.status != "success":
            print(f"[WARN]: PDF CANNOT BE PARSED: {res.input.file.name}, {res.errors}")
            continue
        output_path = output_dir / f"{res.input.file.stem}.md"
        res.document.save_as_markdown(filename=output_path)
        results.append(output_path)
    
    if not results:
        raise FileNotFoundError(f"NO PDFS successfully parsed: {pdf_dir}")
    return results


def convert_docx_raw(docx_dir: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    docx_path = sorted(docx_dir.glob("*.docx"))
    if not docx_path:
        raise FileNotFoundError(f"NO DOCX FILES EXIST IN: {docx_dir}")
    results = []
    convert = DocumentConverter()
    for res in convert.convert_all(docx_path, raises_on_error=False):
        if res.status != "success":
            print(f"[WARN]: DOCX CANNOT BE PARSED {res.input.file.name}: {res.errors}")
            continue
        output_path = output_dir / f"{res.input.file.stem}.md"
        res.document.save_as_markdown(output_path)
        results.append(output_path)
        
    if not results:
        raise FileNotFoundError(f" THERE ARE NO DOCX FILES AVAILABLE TO PARSE: {docx_dir}")
    return results


    
    
    
    
    
def convert_TXT_raw(TXT_dir: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    TXT_path = sorted(TXT_dir.glob("*.txt"))
    if not TXT_path:
        raise FileNotFoundError(f"NO TXT FILES AVAILABLE: {TXT_dir}")
    results = []
    converter = DocumentConverter()
    for res in converter.convert_all(TXT_path, raises_on_error=False):
        if res.status != "success":
            print(f"[WARN]: CANNOT PARSE FILES: {res.input.file.name}: {res.errors}")
            continue
        output_path = output_dir / f"{res.input.file.stem}.md"
        res.document.save_as_markdown(output_path)
        results.append(output_path)
    if not results:
        raise FileNotFoundError(f"TXT FILES CANNOT BE PARSED: {TXT_dir}")
    return results
    
    


if __name__ == "__main__":
    pdf_results_dir = convert_pdf_raw(
        pdf_dir= Path("data/PDFS"),
        output_dir=Path("data/raw")
    )
    print(f"SUCCESSFULLY PARSED ALL PDFS IN: {pdf_results_dir}")
    print(f"TOTAL NUMBER OF PDFS: {len(pdf_results_dir)}")
    
