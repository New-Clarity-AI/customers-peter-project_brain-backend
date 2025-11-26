# back_end/services/chunker.py
import os
from typing import List, Tuple
from datetime import datetime
import hashlib

try:
    import tiktoken
    TOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
except Exception:
    TOKEN_ENCODER = None

CHUNK_TOKENS = int(os.getenv("CHUNK_TOKENS", "600"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))

def _count_tokens(text: str) -> int:
    if TOKEN_ENCODER:
        return len(TOKEN_ENCODER.encode(text))
    return len(text.split())

def chunk_text_by_tokens(text: str, chunk_tokens: int = CHUNK_TOKENS, overlap: int = CHUNK_OVERLAP) -> List[Tuple[str, int, int]]:
    """Return list of tuples: (chunk_text, start_token_index, end_token_index)"""
    if not text:
        return []

    if TOKEN_ENCODER:
        tokens = TOKEN_ENCODER.encode(text)
        n = len(tokens)
        chunks = []
        start = 0
        while start < n:
            end = min(start + chunk_tokens, n)
            chunk_tokens_list = tokens[start:end]
            chunk_text = TOKEN_ENCODER.decode(chunk_tokens_list)
            chunks.append((chunk_text, start, end))
            if end == n:
                break
            start = end - overlap
        return chunks

    # fallback: split by paragraphs
    paras = [p for p in text.split("\n\n") if p.strip()]
    chunks = []
    buffer = ""
    for p in paras:
        if _count_tokens(buffer + " " + p) <= chunk_tokens or not buffer:
            buffer = (buffer + "\n\n" + p).strip()
        else:
            chunks.append((buffer, 0, 0))
            buffer = p
    if buffer:
        chunks.append((buffer, 0, 0))
    return chunks

def compute_chunk_hash(file_id: str, start: int, end: int) -> str:
    h = hashlib.sha256()
    h.update(f"{file_id}:{start}:{end}".encode("utf-8"))
    return h.hexdigest()
