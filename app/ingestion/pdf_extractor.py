import fitz  # PyMuPDF

from app.core.exceptions import ExtractionError


def extract_text_from_pdf(file_bytes: bytes) -> list[dict]:
    """
    Extracts text from a PDF, page by page.
    Returns a list of {"page_number": int, "text": str} dicts.
    Raises ExtractionError for corrupt, encrypted, or empty PDFs.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise ExtractionError(f"Could not open PDF: {e}")

    if doc.is_encrypted:
        doc.close()
        raise ExtractionError("PDF is password-protected and cannot be read")

    if doc.page_count == 0:
        doc.close()
        raise ExtractionError("PDF has no pages")

    pages = []
    for page_number in range(doc.page_count):
        page = doc.load_page(page_number)
        text = page.get_text().strip()
        if text:
            pages.append({"page_number": page_number + 1, "text": text})

    doc.close()

    if not pages:
        raise ExtractionError(
            "No extractable text found — this PDF may be scanned/image-based"
        )

    return pages