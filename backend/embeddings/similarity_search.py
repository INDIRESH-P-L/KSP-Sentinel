import sys
import os
from sqlalchemy.orm import Session

# Add paths to make imports clean
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.database.models import FIR
from embeddings.sentence_transformer import FIRTextEncoder
from embeddings.faiss_index import FIRSimilarityIndex

# Initialize components globally for caching/reuse
_encoder = None
_index = None

def get_encoder_and_index():
    global _encoder, _index
    if _encoder is None:
        _encoder = FIRTextEncoder()
    if _index is None:
        _index = FIRSimilarityIndex()
        # Try to load existing index
        _index.load()
    return _encoder, _index

def build_search_index(db: Session):
    """Fetches all FIRs, encodes their descriptions, builds the index, and saves it"""
    encoder, index = get_encoder_and_index()
    
    # Query all FIRs with descriptions
    firs = db.query(FIR).filter(FIR.description != None).all()
    if not firs:
        print("No FIRs found to index.")
        return False
        
    ids = [f.id for f in firs]
    descriptions = [f.description for f in firs]
    
    # Encode descriptions
    print(f"Encoding {len(descriptions)} FIR descriptions...")
    if encoder.vectorizer is not None:
        # Fit vectorizer on current corpus if fallback TF-IDF model is used
        encoder.fit_fallback(descriptions)
        
    embeddings = encoder.encode(descriptions)
    
    # Reset index and add vectors
    new_index = FIRSimilarityIndex()
    new_index.add_vectors(ids, embeddings)
    new_index.save()
    
    # Update global reference
    global _index
    _index = new_index
    print("Semantic search index built and saved successfully.")
    return True

def search_similar_firs(query_text: str, top_k: int, db: Session):
    """Searches for top_k similar FIRs using the query_text"""
    encoder, index = get_encoder_and_index()
    
    # If index is empty, try building it
    if len(index.ids) == 0:
        success = build_search_index(db)
        if not success:
            return []
        # build_search_index() rebinds the module-level _index to a NEW object, so the
        # `index` captured above still points at the old, empty one. Re-fetch, or this
        # first call after a cold start searches an empty index and silently returns
        # nothing -- which looked like "no similar cases" rather than "not indexed yet".
        encoder, index = get_encoder_and_index()
        if len(index.ids) == 0:
            return []
            
    # Encode query
    query_vector = encoder.encode(query_text)[0]
    
    # Search
    result_ids, scores = index.search(query_vector, top_k)
    
    if not result_ids:
        return []
        
    # Fetch FIR details from database in the exact rank order
    firs_dict = {f.id: f for f in db.query(FIR).filter(FIR.id.in_(result_ids)).all()}
    
    ordered_results = []
    for fid, score in zip(result_ids, scores):
        if fid in firs_dict:
            fir = firs_dict[fid]
            ordered_results.append({
                "fir": fir,
                "score": round(score, 4)
            })
            
    return ordered_results
