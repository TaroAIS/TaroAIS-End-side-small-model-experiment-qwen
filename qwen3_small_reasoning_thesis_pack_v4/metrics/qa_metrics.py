import re
from collections import Counter


def normalize_text(text):
    text = (text or "").strip().lower()
    text = re.sub(r"[\s\t\n\r]+", "", text)
    text = re.sub(r"[，。！？、,.!?;:\"'`（）()\[\]{}<>《》]", "", text)
    return text


def _tokens(text, mode="char"):
    t = normalize_text(text)
    if not t:
        return []
    if mode == "char":
        return [c for c in t]
    return [x for x in t.split(" ") if x]


def exact_match(pred, gold):
    return 1.0 if normalize_text(pred) == normalize_text(gold) else 0.0


def token_f1(pred, gold, mode="char"):
    p = _tokens(pred, mode=mode)
    g = _tokens(gold, mode=mode)
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    cp = Counter(p)
    cg = Counter(g)
    common = cp & cg
    overlap = float(sum(common.values()))
    if overlap <= 0:
        return 0.0
    prec = overlap / float(len(p))
    rec = overlap / float(len(g))
    if prec + rec <= 0:
        return 0.0
    return 2.0 * prec * rec / (prec + rec)


def best_over_gold(pred, gold):
    if isinstance(gold, list):
        em = 0.0
        f1 = 0.0
        for g in gold:
            em = max(em, exact_match(pred, g))
            f1 = max(f1, token_f1(pred, g, mode="char"))
        return em, f1
    return exact_match(pred, gold), token_f1(pred, gold, mode="char")
