import math

def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.asin(math.sqrt(min(1.0, a)))

def perform_st_dbscan(points, eps_km=0.75, eps_hours=6.0, min_samples=3):
    """
    Spatio-temporal DBSCAN in pure Python without numpy.
    points: list of dicts with keys latitude, longitude, hour (0-23), fir_id (optional)
    Returns: {"clusters": [...], "outliers": [...]}
    """
    n = len(points)
    if n < min_samples:
        return {"clusters": [], "outliers": points}

    labels = [-1] * n
    visited = [False] * n
    cluster_id = 0

    def is_neighbor(i, j):
        p1, p2 = points[i], points[j]
        # Spatial distance
        d_km = _haversine_km(p1["latitude"], p1["longitude"], p2["latitude"], p2["longitude"])
        if d_km > eps_km:
            return False
        # Circular hour distance
        h1, h2 = float(p1["hour"]), float(p2["hour"])
        h_diff = abs(h1 - h2)
        h_dist = min(h_diff, 24.0 - h_diff)
        return h_dist <= eps_hours

    def region_query(i):
        return [j for j in range(n) if is_neighbor(i, j)]

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        neighbors = region_query(i)
        if len(neighbors) < min_samples:
            continue

        labels[i] = cluster_id
        seed_set = list(neighbors)
        seen = set(seed_set)
        seen.add(i)

        idx = 0
        while idx < len(seed_set):
            j = seed_set[idx]
            idx += 1
            if not visited[j]:
                visited[j] = True
                j_neighbors = region_query(j)
                if len(j_neighbors) >= min_samples:
                    for k in j_neighbors:
                        if k not in seen:
                            seen.add(k)
                            seed_set.append(k)
            if labels[j] == -1:
                labels[j] = cluster_id
        cluster_id += 1

    clusters = []
    outliers = []
    grouped = {}
    for i, label in enumerate(labels):
        if label == -1:
            outliers.append(points[i])
        else:
            grouped.setdefault(label, []).append(points[i])

    for cid, member_points in grouped.items():
        avg_lat = sum(p["latitude"] for p in member_points) / len(member_points)
        avg_lng = sum(p["longitude"] for p in member_points) / len(member_points)
        
        sin_sum = sum(math.sin(float(p["hour"]) / 24.0 * 2.0 * math.pi) for p in member_points)
        cos_sum = sum(math.cos(float(p["hour"]) / 24.0 * 2.0 * math.pi) for p in member_points)
        mean_hour = (math.degrees(math.atan2(sin_sum, cos_sum)) / 360.0 * 24.0) % 24.0

        clusters.append({
            "cluster_id": int(cid),
            "center": [round(avg_lat, 6), round(avg_lng, 6)],
            "size": len(member_points),
            "dominant_hour": round(float(mean_hour), 1),
            "points": [[p["latitude"], p["longitude"]] for p in member_points],
            "fir_ids": [p.get("fir_id") for p in member_points if p.get("fir_id") is not None],
        })

    return {"clusters": clusters, "outliers": outliers}
