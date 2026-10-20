from dataclasses import dataclass


@dataclass
class TextChunk:
    page_number: int
    text: str


def chunk_pages(pages, chunk_size=800, overlap=150):
    """Split each page into chunks of about `chunk_size` characters.

    Chunks overlap by `overlap` characters so a sentence cut at a boundary
    still appears whole in one of the chunks. Chunks never cross pages,
    so every chunk has exactly one page number to cite.
    """
    chunks = []
    for page_number, raw_text in pages:
        text = " ".join(raw_text.split())  # collapse extra spaces and line breaks
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))

            # Try not to cut in the middle of a sentence or word
            if end < len(text):
                cut = text.rfind(". ", start, end)
                if cut < start + chunk_size // 2:
                    cut = text.rfind(" ", start, end)
                if cut > start:
                    end = cut + 1

            piece = text[start:end].strip()
            if piece:
                chunks.append(TextChunk(page_number=page_number, text=piece))

            if end >= len(text):
                break
            next_start = end - overlap
            start = next_start if next_start > start else end

    return chunks
