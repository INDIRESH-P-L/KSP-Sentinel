"""Feature 2 — IPC/BNS section suggestion by retrieval.

There is no labelled complaint->section training data in this repo, so this is a
*retrieval* system, not a classifier: a curated reference corpus of section
descriptions (data/ipc_bns_sections.json) is embedded once, and an incoming complaint
is matched against it by cosine similarity. Nothing is learned or inferred beyond
"this complaint reads like this section's description", which is exactly as much as
the available data supports — a trained classifier here would be a black box with no
ground truth behind it.

Reuses the existing pipeline: FIRTextEncoder for encoding and FIRSimilarityIndex for
the cosine search.

    IMPORTANT — persistence isolation.
    FIRTextEncoder.fit_fallback() writes the fitted vectorizer to the *shared*
    datasets/embeddings/tfidf_vectorizer.pkl, which the FIR semantic search owns.
    Fitting that shared file on legal-section text would silently repoint
    /api/crimes/search and the duplicate check at the wrong vocabulary. So in the
    TF-IDF fallback path we hand the encoder a FRESH vectorizer and redirect its
    persistence to a separate file before fitting. Likewise FIRSimilarityIndex is used
    purely in memory here -- .save() is never called, so the FIR index files on disk
    are never touched.
"""
import json
import os
import sys
import threading

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.config import settings
from embeddings.sentence_transformer import FIRTextEncoder, HAS_TRANSFORMERS
from embeddings.faiss_index import FIRSimilarityIndex, HAS_FAISS

REFERENCE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ipc_bns_sections.json")
# Deliberately NOT the shared tfidf_vectorizer.pkl -- see the module docstring.
SECTION_VECTORIZER_FILE = os.path.join("datasets", "embeddings", "section_tfidf_vectorizer.pkl")

_lock = threading.Lock()
_state = {"sections": None, "index": None, "encoder": None, "meta": None}


def _corpus_text(entry: dict) -> str:
    """What actually gets embedded for a section.

    Title + description + keywords, with the keywords repeated into the string
    because under TF-IDF a term only counts if it appears -- the keyword list is how
    colloquial complaint vocabulary ("otp", "chain snatch") reaches the vector at all,
    since formal section prose never contains those words.
    """
    parts = [entry.get("title", ""), entry.get("description", "")]
    kws = entry.get("keywords") or []
    parts.append(" ".join(kws))
    parts.append(entry.get("category", ""))
    return " ".join(p for p in parts if p).strip()


def load_reference() -> tuple[list[dict], dict]:
    with open(REFERENCE_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("sections", []), data.get("_meta", {})


def _build():
    """Builds the in-memory section index. Called once per process, lazily."""
    sections, meta = load_reference()
    corpus = [_corpus_text(s) for s in sections]

    encoder = FIRTextEncoder()
    if encoder.model is None:
        # TF-IDF fallback: isolate persistence, then fit on the SECTION corpus so the
        # vocabulary is offence language rather than whatever the FIR corpus happened
        # to contain.
        from sklearn.feature_extraction.text import TfidfVectorizer
        os.makedirs(os.path.dirname(SECTION_VECTORIZER_FILE), exist_ok=True)
        encoder.fallback_file = SECTION_VECTORIZER_FILE
        encoder.vectorizer = TfidfVectorizer(max_features=384, stop_words="english")
        encoder.fit_fallback(corpus)

    vectors = encoder.encode(corpus)

    index = FIRSimilarityIndex(dimension=vectors.shape[1] if len(vectors) else 384)
    index.add_vectors(list(range(len(sections))), vectors)   # ids are positional
    # NOTE: index.save() is intentionally never called -- see module docstring.

    _state.update({"sections": sections, "index": index, "encoder": encoder, "meta": meta})


def get_index():
    if _state["index"] is None:
        with _lock:
            if _state["index"] is None:
                _build()
    return _state["sections"], _state["index"], _state["encoder"], _state["meta"]


def reset_index():
    """Drops the cached index so the next call re-reads the reference file (used after
    editing data/ipc_bns_sections.json without a restart, and by tests)."""
    with _lock:
        _state.update({"sections": None, "index": None, "encoder": None, "meta": None})


def embedding_backend() -> str:
    enc = "sentence-transformers" if HAS_TRANSFORMERS else "tfidf-fallback"
    idx = "faiss" if HAS_FAISS else "numpy-cosine-fallback"
    return f"{enc}+{idx}"


def suggest_sections(text: str, top_k: int | None = None, min_confidence: float | None = None) -> list[dict]:
    """Ranked section candidates for a free-text complaint.

    `confidence` is the raw cosine similarity against the reference description -- a
    similarity, NOT a calibrated probability. It is comparable between candidates in
    one response but not across different embedding backends.
    """
    top_k = top_k or settings.SECTION_SUGGESTION_TOP_K
    min_conf = settings.SECTION_SUGGESTION_MIN_CONFIDENCE if min_confidence is None else min_confidence

    sections, index, encoder, _meta = get_index()
    if not sections:
        return []

    qvec = encoder.encode(text)[0]
    # Over-fetch, then trim after filtering so a low-scoring hit can't occupy a slot.
    ids, scores = index.search(qvec, min(len(sections), max(top_k * 3, top_k)))
    if not ids:
        return []

    # Relative floor: anything far below the best match is noise padding out the
    # top-k, not a real alternative charge. Judged as a fraction of the top score
    # because the absolute scale moves with the embedding backend.
    top_score = max(float(s) for s in scores)
    # Guarded against a negative best score. Cosine similarity is signed, and
    # `top * 0.20` INVERTS when top < 0 (a best of -0.4 gives a floor of -0.08, which
    # is greater than the score it was derived from) -- so the filter below rejected
    # every candidate including the best one, and the endpoint returned nothing at all
    # rather than its weakest-but-real suggestions.
    rel_floor = top_score * settings.SECTION_SUGGESTION_RELATIVE_FLOOR if top_score > 0 else float("-inf")

    out = []
    for pos, score in zip(ids, scores):
        if score < min_conf or score < rel_floor:
            continue
        entry = sections[pos]
        out.append({
            "rank": len(out) + 1,
            "suggested_section": entry.get("bns_section"),
            "bns_section": entry.get("bns_section"),
            "ipc_section": entry.get("ipc_section"),
            "title": entry.get("title"),
            "category": entry.get("category"),
            "confidence": round(float(score), 4),
            "reference_description": entry.get("description"),
        })
        if len(out) >= top_k:
            break
    return out
