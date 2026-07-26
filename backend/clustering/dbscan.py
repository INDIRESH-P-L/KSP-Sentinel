import math

def perform_dbscan(coordinates, eps=0.015, min_samples=3):
    """
    Pure Python DBSCAN implementation matching scikit-learn DBSCAN API.
    coordinates: List of lists/tuples [[lat, lng], [lat, lng], ...]
    eps: Radius in degrees (~1.5 km)
    min_samples: Minimum points to form a cluster
    Returns: {"clusters": [...], "outliers": [...]}
    """
    if len(coordinates) < min_samples:
        return {"clusters": [], "outliers": [list(c) for c in coordinates]}

    pts = [list(c) for c in coordinates]
    n = len(pts)
    labels = [-1] * n
    cluster_id = 0

    def region_query(i):
        p = pts[i]
        neighbors = []
        for j, q in enumerate(pts):
            if math.hypot(p[0] - q[0], p[1] - q[1]) <= eps:
                neighbors.append(j)
        return neighbors

    for i in range(n):
        if labels[i] != -1:
            continue
        neighbors = region_query(i)
        if len(neighbors) < min_samples:
            labels[i] = -1
        else:
            labels[i] = cluster_id
            seeds = [j for j in neighbors if j != i]
            while seeds:
                curr = seeds.pop(0)
                if labels[curr] == -1:
                    labels[curr] = cluster_id
                if labels[curr] != -1 and labels[curr] != cluster_id:
                    continue
                labels[curr] = cluster_id
                curr_neighbors = region_query(curr)
                if len(curr_neighbors) >= min_samples:
                    for neighbor in curr_neighbors:
                        if labels[neighbor] in (-1, None):
                            seeds.append(neighbor)
            cluster_id += 1

    clusters = []
    outliers = []
    grouped = {}
    for i, label in enumerate(labels):
        if label == -1:
            outliers.append(pts[i])
        else:
            grouped.setdefault(label, []).append(pts[i])

    for cid, points in grouped.items():
        avg_lat = sum(p[0] for p in points) / len(points)
        avg_lng = sum(p[1] for p in points) / len(points)
        clusters.append({
            "cluster_id": cid,
            "center": [round(avg_lat, 6), round(avg_lng, 6)],
            "size": len(points),
            "points": points
        })

    return {"clusters": clusters, "outliers": outliers}
