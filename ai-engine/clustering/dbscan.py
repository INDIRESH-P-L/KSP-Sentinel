import numpy as np
from sklearn.cluster import DBSCAN

def perform_dbscan(coordinates, eps=0.015, min_samples=3):
    """
    coordinates: List of lists/tuples [[lat, lng], [lat, lng], ...]
    eps: Radius in degrees (~1.5 km)
    min_samples: Minimum points to form a cluster
    Returns: List of dicts representing clusters and list of outliers
    """
    if len(coordinates) < min_samples:
        return {"clusters": [], "outliers": [list(c) for c in coordinates]}
        
    X = np.array(coordinates)
    
    # Fit DBSCAN
    db = DBSCAN(eps=eps, min_samples=min_samples)
    labels = db.fit_predict(X)
    
    unique_labels = set(labels)
    clusters = []
    outliers = []
    
    for label in unique_labels:
        cluster_idx = np.where(labels == label)[0]
        points = X[cluster_idx].tolist()
        
        if label == -1:
            outliers = points
        else:
            # Calculate centroid for visualization
            centroid = np.mean(X[cluster_idx], axis=0).tolist()
            clusters.append({
                "cluster_id": int(label),
                "center": [float(centroid[0]), float(centroid[1])],
                "size": len(points),
                "points": points
            })
            
    return {
        "clusters": clusters,
        "outliers": outliers
    }
