from pypdf import PdfReader


def extract_pages(file_path):
    """Return a list of (page_number, text) for pages that contain text,
    plus the total page count."""
    reader = PdfReader(file_path)
    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((page_number, text))
    return pages, len(reader.pages)
