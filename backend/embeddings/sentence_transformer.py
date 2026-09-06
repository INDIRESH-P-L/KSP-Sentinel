"""Text -> vector encoding for FIR similarity search.

Three backends, in descending order of quality, chosen by what is actually
importable at runtime:

  1. sentence-transformers (all-MiniLM-L6-v2)  -- real semantic embeddings.
  2. scikit-learn TF-IDF                       -- lexical, corpus-dependent.
  3. built-in hashing encoder                  -- lexical, no dependencies.

On the AppSail deployment only (3) exists: requirements.txt deliberately drops
sentence-transformers (90MB model download at boot) and scikit-learn/faiss (native
builds), and neither is vendored in backend/vendor/. So the hashing encoder is the
production path, not a theoretical last resort, and it is written to be a usable
embedding rather than a placeholder.

Scores from the three backends are NOT on the same scale and must never be compared
or thresholded against each other -- see DUPLICATE_SIMILARITY_THRESHOLD vs
DUPLICATE_SIMILARITY_THRESHOLD_TFIDF in app/config.py. `backend` / `backend_stamp()`
report which one is live so callers (and the persisted index) can say so.
"""
import hashlib
import os
import pickle
import re

import numpy as np

# Check if sentence-transformers is installed, otherwise fall back to scikit-learn TF-IDF
try:
    from sentence_transformers import SentenceTransformer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    TfidfVectorizer = None

# Every backend emits this width so vectors from one are at least *shaped* like
# vectors from another; the index stamps the backend name to stop them being mixed.
EMBEDDING_DIM = 384

BACKEND_TRANSFORMER = "sentence-transformers"
BACKEND_TFIDF = "tfidf"
# Bump the version suffix whenever the hashing scheme below changes in any way that
# moves a token to a different bucket (digest, dimension, tokenisation, n-grams,
# weights). Any index persisted under an older suffix is coordinate-space garbage
# against the new one and the stamp check in faiss_index.py will reject it.
BACKEND_HASHING = "hashing-v1"

# Deliberately tiny: this mirrors the intent of TfidfVectorizer(stop_words="english")
# on the TF-IDF path. Without it every pair of English sentences shares "the/and/was"
# buckets and the whole corpus looks weakly similar to everything, which flattens the
# ranking the relative floor in section_suggestion depends on.
_STOPWORDS = frozenset("""
a an the and or but if of in on at to for from by with without into onto over under
is are was were be been being am do does did done has have had having
this that these those it its he she they them his her their we you i my our your
as not no so than then there here when while about against between during after before
""".split())

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Character n-grams let near-miss spellings and morphological variants collide
# ("snatching"/"snatched", "moblie"/"mobile"), which pure word hashing cannot do.
# They are weighted below whole words because they are far more numerous and much
# less discriminative -- at weight 1.0 they drown the word channel entirely.
_NGRAM_SIZE = 3
_NGRAM_WEIGHT = 0.35
_NGRAM_MIN_WORD_LEN = 4


def _bucket(token: str) -> int:
    """Stable bucket for a token.

    This used to be `abs(hash(token)) % 384`. Python randomises str.__hash__ per
    process (PYTHONHASHSEED), so the same text encoded to a different vector after
    every restart and on every AppSail instance: a query was scored against index
    vectors from an unrelated coordinate space and the search returned effectively
    random FIRs at plausible-looking cosine scores. blake2b is identical across
    processes, restarts and machines.
    """
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % EMBEDDING_DIM


def _char_ngrams(word: str):
    padded = f" {word} "
    for i in range(len(padded) - _NGRAM_SIZE + 1):
        yield padded[i:i + _NGRAM_SIZE]


def hash_embed(text: str) -> np.ndarray:
    """Deterministic bag-of-hashed-features vector, L2-normalised.

    Normalisation is not cosmetic: both index backends score by inner product and
    treat it as cosine similarity, so an unnormalised vector makes a long document
    beat a relevant short one purely on length.
    """
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    for word in _TOKEN_RE.findall(str(text).lower()):
        if word in _STOPWORDS or len(word) < 2:
            continue
        vec[_bucket(word)] += 1.0
        if len(word) >= _NGRAM_MIN_WORD_LEN:
            for gram in _char_ngrams(word):
                vec[_bucket("#" + gram)] += _NGRAM_WEIGHT

    # Sublinear term frequency: a word repeated ten times is not ten times the
    # evidence, and without damping one repeated word dominates the direction.
    np.sqrt(vec, out=vec)

    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


def _fit_width(vectors: np.ndarray) -> np.ndarray:
    """Pads or truncates to EMBEDDING_DIM so every backend returns the same width."""
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)
    width = vectors.shape[1]
    if width == EMBEDDING_DIM:
        return vectors
    fitted = np.zeros((vectors.shape[0], EMBEDDING_DIM), dtype=np.float32)
    keep = min(width, EMBEDDING_DIM)
    fitted[:, :keep] = vectors[:, :keep]
    return fitted


class FIRTextEncoder:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self.vectorizer = None
        # True only once the vectorizer has a vocabulary. An unfitted TfidfVectorizer
        # raises on transform(), and that exception used to be swallowed so encode()
        # quietly changed backend mid-corpus -- half the vectors TF-IDF, half hashed.
        self.vectorizer_fitted = False
        self.fallback_file = os.path.join("datasets", "embeddings", "tfidf_vectorizer.pkl")

        if HAS_TRANSFORMERS:
            try:
                # Load pre-trained MiniLM
                self.model = SentenceTransformer(model_name)
            except Exception as e:
                print(f"Failed to load sentence-transformer model, using TF-IDF fallback. Error: {e}")
                self._init_tfidf()
        else:
            self._init_tfidf()

    def _init_tfidf(self):
        if not (HAS_SKLEARN and TfidfVectorizer is not None):
            # Nothing to set up: encode() uses the built-in hashing encoder.
            self.vectorizer = None
            return

        self.vectorizer = TfidfVectorizer(max_features=EMBEDDING_DIM, stop_words="english")
        if os.path.exists(self.fallback_file):
            try:
                with open(self.fallback_file, "rb") as f:
                    loaded = pickle.load(f)
                # A pickle without a vocabulary is an unfitted (or foreign) object;
                # keeping it would look fitted to nobody and still fail at transform().
                if getattr(loaded, "vocabulary_", None):
                    self.vectorizer = loaded
                    self.vectorizer_fitted = True
                else:
                    print(f"Ignoring unfitted TF-IDF vectorizer at {self.fallback_file}.")
            except Exception as e:
                print(f"Could not load TF-IDF vectorizer from {self.fallback_file}: {e}")

    @property
    def backend(self) -> str:
        """The backend encode() will actually use for the next call."""
        if self.model is not None:
            return BACKEND_TRANSFORMER
        if self.vectorizer is not None and self.vectorizer_fitted:
            return BACKEND_TFIDF
        return BACKEND_HASHING

    def backend_stamp(self) -> str:
        """Identity of the vector space this encoder produces.

        Stamped into a persisted index so a later process can refuse to search vectors
        it did not produce. Anything that changes the geometry must change this string.
        """
        return f"{self.backend}/dim={EMBEDDING_DIM}"

    def needs_fitting(self) -> bool:
        """True when the caller must supply a corpus before encoding is meaningful."""
        return self.vectorizer is not None and not self.vectorizer_fitted

    def fit_fallback(self, corpus):
        """Fits the TF-IDF vectorizer if using fallback model.

        No-op for the transformer and hashing backends: neither learns anything from a
        corpus, and the hashing encoder is corpus-independent by construction (which is
        what makes it safe across AppSail instances).
        """
        if self.vectorizer is None or not corpus:
            return

        self.vectorizer.fit(corpus)
        self.vectorizer_fitted = True

        # Persist only as a cache. A read-only or ephemeral container filesystem must
        # not take the search down -- the vectorizer is already fitted in memory -- but
        # it must be visible in the logs, because it means every process refits.
        try:
            directory = os.path.dirname(self.fallback_file)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.fallback_file, "wb") as f:
                pickle.dump(self.vectorizer, f)
        except OSError as e:
            print(f"Could not persist TF-IDF vectorizer to {self.fallback_file}: {e}")

    def encode(self, texts):
        """Encodes list of strings into array of shape (num_texts, EMBEDDING_DIM)"""
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)

        backend = self.backend
        if backend == BACKEND_TRANSFORMER:
            return _fit_width(self.model.encode(texts, convert_to_numpy=True).astype(np.float32))
        if backend == BACKEND_TFIDF:
            return _fit_width(self.vectorizer.transform(texts).toarray())
        return np.vstack([hash_embed(t) for t in texts]).astype(np.float32)
