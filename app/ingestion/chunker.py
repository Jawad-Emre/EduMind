from app.core.exceptions import ExtractionError

CHUNK_SIZE = 600              # target characters per chunk (soft target, not a hard ceiling)
CHUNK_OVERLAP_SENTENCES = 2   # trailing sentences repeated into the next chunk, for context continuity
MIN_CHUNK_SIZE = 150           # chunks smaller than this get merged into the previous chunk

import nltk

def _split_into_sentences(text: str) -> list[str]:
    """Sentence splitter using NLTK's punkt tokenizer — abbreviation-aware
    (handles 'Dr. Smith', titles, etc.), more reliable than raw regex for
    chunk boundaries. Not linguistically perfect on every edge case
    (e.g. 'e.g.' mid-sentence), but strictly better than punctuation-only
    splitting."""
    text = text.strip()
    if not text:
        return []
    sentences = nltk.sent_tokenize(text)
    return [s.strip() for s in sentences if s.strip()]


def _recursive_split(text: str, max_size: int) -> list[str]:
    """
    Tries paragraph -> sentence -> word splitting, in that order.
    Only recurses into a piece if it's still too big after a given separator.
    Falls back to a hard character cut only if no separator works at all.
    """
    if len(text) <= max_size: #600
        return [text]

    for separator in ["\n\n", ". ", " "]:
        if separator in text:
            parts = text.split(separator)
            pieces = []
            current = ""
            for part in parts:
                candidate = current + (separator if current else "") + part
                if len(candidate) <= max_size:
                    current = candidate
                else:
                    if current:
                        pieces.append(current)
                    current = part
            if current:
                pieces.append(current)

            final_pieces = []
            for piece in pieces:
                if len(piece) > max_size:
                    final_pieces.extend(_recursive_split(piece, max_size))
                else:
                    final_pieces.append(piece)
            return final_pieces

    # last resort: hard cut by character count (should rarely trigger on real text)
    return [text[i:i + max_size] for i in range(0, len(text), max_size)]
    #Equvalent to above list comprehension
        # for i in range(0, len(text), max_size):
        #     piece = text[i : i + max_size]
        #     result.append(piece)
        # return result


def chunk_pages(pages: list[dict]) -> list[dict]:
    """
    Takes extractor output: [{"page_number": int, "text": str}, ...]
    Returns: [{"page_number": int, "chunk_index": int, "content": str}, ...]
    """
    if not pages:
        raise ExtractionError("No pages provided for chunking")

    all_chunks: list[dict] = []
    chunk_index = 0
    carry_over_sentences: list[str] = []

    for page in pages:
        page_number = page["page_number"]
        text = page["text"]

        raw_pieces = _recursive_split(text, CHUNK_SIZE)

        for piece in raw_pieces:
            sentences = _split_into_sentences(piece)
            if not sentences:
                continue # empty/whitespace-only, skip it —> move to the next piece,

            content = " ".join(carry_over_sentences + sentences).strip()
            if not content:
                continue

            if len(content) < MIN_CHUNK_SIZE and all_chunks:
                all_chunks[-1]["content"] += " " + content #last chunk + merge small chunk into previous one
            else:
                all_chunks.append({
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                    "content": content,
                })
                chunk_index += 1
            #overlap for the next piece in the loop:
            carry_over_sentences = (
                sentences[-CHUNK_OVERLAP_SENTENCES:]
                if len(sentences) >= CHUNK_OVERLAP_SENTENCES
                else sentences
            )

    if not all_chunks:
        raise ExtractionError("Chunking produced no usable content")

    return all_chunks