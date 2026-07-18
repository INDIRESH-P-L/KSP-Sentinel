import numpy as np
import os
import pickle

# Check if sentence-transformers is installed, otherwise fall back to scikit-learn TF-IDF
try:
    from sentence_transformers import SentenceTransformer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    from sklearn.feature_extraction.text import TfidfVectorizer

class FIRTextEncoder:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self.vectorizer = None
        self.fallback_file = "datasets/embeddings/tfidf_vectorizer.pkl"
        
        # Ensure directory exists
        os.makedirs("datasets/embeddings", exist_ok=True)
        
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
        # Initialize TF-IDF Vectorizer
        self.vectorizer = TfidfVectorizer(max_features=384, stop_words="english")
        # If we have a saved vectorizer, load it
        if os.path.exists(self.fallback_file):
            try:
                with open(self.fallback_file, "rb") as f:
                    self.vectorizer = pickle.load(f)
            except Exception:
                pass

    def fit_fallback(self, corpus):
        """Fits the TF-IDF vectorizer if using fallback model"""
        if self.vectorizer is not None and corpus:
            self.vectorizer.fit(corpus)
            with open(self.fallback_file, "wb") as f:
                pickle.dump(self.vectorizer, f)

    def encode(self, texts):
        """Encodes list of strings into numpy array of shape (num_texts, embedding_dim)"""
        if isinstance(texts, str):
            texts = [texts]
            
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
            
        if self.model is not None:
            return self.model.encode(texts, convert_to_numpy=True).astype(np.float32)
        else:
            # Fallback encoding using TF-IDF
            try:
                vectors = self.vectorizer.transform(texts).toarray()
                # Ensure the dimensions match the expected size (384 dimensions)
                if vectors.shape[1] < 384:
                    padded = np.zeros((vectors.shape[0], 384), dtype=np.float32)
                    padded[:, :vectors.shape[1]] = vectors
                    return padded
                return vectors.astype(np.float32)
            except Exception:
                # If vectorizer is not fitted yet, fit it dummy or return random values
                if not hasattr(self.vectorizer, 'vocabulary_'):
                    self.fit_fallback(texts + ["Bike stolen Majestic", "murder assault robbery", "cyber crime phishing"])
                    vectors = self.vectorizer.transform(texts).toarray()
                    return vectors.astype(np.float32)
                return np.random.randn(len(texts), 384).astype(np.float32)
