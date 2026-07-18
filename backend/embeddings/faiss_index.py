import numpy as np
import os
import pickle

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

class FIRSimilarityIndex:
    def __init__(self, dimension=384):
        self.dimension = dimension
        self.index_file = "datasets/embeddings/faiss_index.bin"
        self.metadata_file = "datasets/embeddings/metadata.pkl"
        
        self.ids = []  # List of FIR database IDs corresponding to vectors
        
        if HAS_FAISS:
            self.index = faiss.IndexFlatIP(dimension) # Inner Product for cosine similarity (if normalized)
        else:
            self.index = None
            self.vectors = [] # NumPy fallback array

    def add_vectors(self, ids, vectors):
        """Adds vectors and their corresponding database IDs to the index"""
        if len(ids) != len(vectors):
            raise ValueError("Size of IDs must match size of vectors")
            
        if len(vectors) == 0:
            return
            
        vectors = np.array(vectors).astype(np.float32)
        
        # Normalize vectors for Cosine Similarity (Inner Product of L2 normalized is Cosine similarity)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10 # Avoid division by zero
        normalized_vectors = vectors / norms
        
        self.ids.extend(ids)
        
        if HAS_FAISS:
            self.index.add(normalized_vectors)
        else:
            if len(self.vectors) == 0:
                self.vectors = normalized_vectors
            else:
                self.vectors = np.vstack([self.vectors, normalized_vectors])

    def search(self, query_vector, top_k=20):
        """Searches index for query_vector and returns (indices, scores)"""
        query_vector = np.array(query_vector).astype(np.float32).reshape(1, -1)
        # Normalize query vector
        norm = np.linalg.norm(query_vector)
        if norm > 0:
            query_vector = query_vector / norm
            
        if len(self.ids) == 0:
            return [], []
            
        actual_k = min(top_k, len(self.ids))
        
        if HAS_FAISS:
            scores, indices = self.index.search(query_vector, actual_k)
            # Map indices back to FIR IDs
            result_ids = [self.ids[idx] for idx in indices[0] if idx != -1]
            result_scores = [float(score) for score in scores[0][:len(result_ids)]]
            return result_ids, result_scores
        else:
            # NumPy Cosine Similarity fallback
            similarities = np.dot(self.vectors, query_vector.T).flatten()
            top_indices = np.argsort(similarities)[::-1][:actual_k]
            
            result_ids = [self.ids[idx] for idx in top_indices]
            result_scores = [float(similarities[idx]) for idx in top_indices]
            return result_ids, result_scores

    def save(self):
        """Saves index and metadata to files"""
        os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
        
        # Save metadata
        with open(self.metadata_file, "wb") as f:
            pickle.dump(self.ids, f)
            
        if HAS_FAISS:
            faiss.write_index(self.index, self.index_file)
        else:
            with open(self.index_file, "wb") as f:
                pickle.dump(self.vectors, f)

    def load(self):
        """Loads index and metadata from files"""
        if not os.path.exists(self.metadata_file) or not os.path.exists(self.index_file):
            return False
            
        try:
            with open(self.metadata_file, "rb") as f:
                self.ids = pickle.load(f)
                
            if HAS_FAISS:
                self.index = faiss.read_index(self.index_file)
            else:
                with open(self.index_file, "rb") as f:
                    self.vectors = pickle.load(f)
            return True
        except Exception as e:
            print(f"Error loading index: {e}")
            return False
