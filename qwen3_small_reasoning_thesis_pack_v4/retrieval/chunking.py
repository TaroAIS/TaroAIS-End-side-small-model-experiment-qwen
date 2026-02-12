import re


def _split_text(text, chunk_size, overlap):
    text = text or ""
    if chunk_size <= 0:
        chunk_size = 512
    if overlap < 0:
        overlap = 0
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 4)

    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(text_len, start + chunk_size)
        piece = text[start:end]
        if piece.strip():
            chunks.append((start, end, piece))
        if end >= text_len:
            break
        start = end - overlap
    return chunks


def build_chunks_from_dataset(rows, chunk_size=512, overlap=128):
    out = []
    for sample in rows:
        sid = sample.get("id", "unknown")
        docs = sample.get("documents", [])
        for doc_idx, doc in enumerate(docs):
            doc_id = doc.get("doc_id", "{}_d{}".format(sid, doc_idx))
            text = doc.get("text", "")
            for i, (st, ed, piece) in enumerate(_split_text(text, chunk_size, overlap)):
                chunk_id = "{}_{}_{}".format(sid, doc_id, i)
                out.append(
                    {
                        "sample_id": sid,
                        "doc_id": doc_id,
                        "chunk_id": chunk_id,
                        "offset_start": int(st),
                        "offset_end": int(ed),
                        "text": piece,
                    }
                )
    return out


def build_chunks_from_documents(documents, sample_id="runtime", chunk_size=512, overlap=128):
    rows = [{"id": sample_id, "documents": documents}]
    return build_chunks_from_dataset(rows, chunk_size=chunk_size, overlap=overlap)


def normalize_text(text):
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text
