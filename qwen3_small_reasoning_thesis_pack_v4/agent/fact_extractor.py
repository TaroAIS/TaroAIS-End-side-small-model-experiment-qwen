

def extract_facts_from_chunks(chunks, limit=6):
    facts = []
    for i, c in enumerate(chunks[: max(1, int(limit))]):
        text = (c.get("text", "") or "").strip()
        if not text:
            continue
        summary = text[:80]
        fact = {
            "fact_id": "fact_{:04d}".format(i + 1),
            "type": "summary",
            "content": summary,
            "evidence": {
                "doc_id": c.get("doc_id", ""),
                "chunk_id": c.get("chunk_id", ""),
            },
            "confidence": float(max(0.0, min(1.0, c.get("score", 0.5) if isinstance(c.get("score", 0.5), (int, float)) else 0.5))),
        }
        facts.append(fact)
    return facts
