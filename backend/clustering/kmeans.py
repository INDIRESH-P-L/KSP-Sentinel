import math

try:
    import numpy as np
    from sklearn.cluster import KMeans
    HAS_KMEANS = True
except ImportError:
    HAS_KMEANS = False

def perform_kmeans(coordinates, num_clusters=5):
    """
    coordinates: List of lists/tuples [[lat, lng], [lat, lng], ...]
    Returns: List of dicts representing clusters with center and size
    """
    if len(coordinates) < num_clusters:
        return [{"cluster_id": i, "center": list(coord), "size": 1, "points": [list(coord)]} for i, coord in enumerate(coordinates)]
        
    if HAS_KMEANS:
        X = np.array(coordinates)
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

    # Pure Python fallback
    pts = [list(c) for c in coordinates]
    chunk_size = max(1, len(pts) // num_clusters)
    clusters = []
    for i in range(num_clusters):
        sub_pts = pts[i * chunk_size : (i + 1) * chunk_size] if i < num_clusters - 1 else pts[i * chunk_size :]
        if not sub_pts:
            continue
        avg_lat = sum(p[0] for p in sub_pts) / len(sub_pts)
        avg_lng = sum(p[1] for p in sub_pts) / len(sub_pts)
        clusters.append({
            "cluster_id": i,
            "center": [round(avg_lat, 6), round(avg_lng, 6)],
            "size": len(sub_pts),
            "points": sub_pts
        })
    return clusters
