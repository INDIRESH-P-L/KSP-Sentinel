import numpy as np
from sklearn.cluster import KMeans

def perform_kmeans(coordinates, num_clusters=5):
    """
    coordinates: List of lists/tuples [[lat, lng], [lat, lng], ...]
    Returns: List of dicts representing clusters with center and size
    """
    if len(coordinates) < num_clusters:
        # Fallback if too few coordinates
        return [{"center": list(coord), "size": 1, "points": [list(coord)]} for coord in coordinates]
        
    X = np.array(coordinates)
    
    # Fit KMeans
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init='auto')
    labels = kmeans.fit_predict(X)
    centers = kmeans.cluster_centers_
    
    clusters = []
    for i in range(num_clusters):
        cluster_idx = np.where(labels == i)[0]
        cluster_points = X[cluster_idx].tolist()
        
        clusters.append({
            "cluster_id": i,
            "center": [float(centers[i][0]), float(centers[i][1])],
            "size": len(cluster_points),
            "points": cluster_points
        })
        
    return clusters
