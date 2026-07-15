import numpy as np


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlambda / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def perform_st_dbscan(points, eps_km=0.75, eps_hours=6.0, min_samples=3):
    """
    Spatio-temporal DBSCAN (Birant & Kut, 2007): two incidents are neighbors only if
    they are BOTH within eps_km of each other AND within eps_hours of each other in
    time-of-day — unlike plain DBSCAN, which only sees the spatial axis and would happily
    cluster a 3am burglary with an unrelated 3pm one just because they're on the same street.

    points: list of dicts with keys latitude, longitude, hour (0-23), fir_id (optional)
    Returns: {"clusters": [...], "outliers": [...]}
    """
    n = len(points)
    if n < min_samples:
        return {"clusters": [], "outliers": points}

    lats = np.array([p["latitude"] for p in points])
    lons = np.array([p["longitude"] for p in points])
    hours = np.array([p["hour"] for p in points], dtype=float)

    # Circular hour distance (23:00 and 01:00 are 2 hours apart, not 22)
    hour_diff = np.abs(hours[:, None] - hours[None, :])
    hour_dist = np.minimum(hour_diff, 24 - hour_diff)

    spatial_dist = _haversine_km(lats[:, None], lons[:, None], lats[None, :], lons[None, :])

    neighbor_mask = (spatial_dist <= eps_km) & (hour_dist <= eps_hours)

    labels = np.full(n, -1, dtype=int)
    visited = np.zeros(n, dtype=bool)
    cluster_id = 0

    def region_query(idx):
        return np.where(neighbor_mask[idx])[0]

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
    for label in set(labels.tolist()):
        idxs = np.where(labels == label)[0]
        member_points = [points[i] for i in idxs]
        if label == -1:
            outliers = member_points
            continue

        centroid = [float(lats[idxs].mean()), float(lons[idxs].mean())]
        member_hours = hours[idxs]
        # Circular mean hour so a cluster spanning 23:00-01:00 reports ~00:00, not 12:00
        mean_hour = (np.degrees(np.arctan2(
            np.mean(np.sin(member_hours / 24 * 2 * np.pi)),
            np.mean(np.cos(member_hours / 24 * 2 * np.pi))
        )) / 360 * 24) % 24

        clusters.append({
            "cluster_id": int(label),
            "center": centroid,
            "size": len(member_points),
            "dominant_hour": round(float(mean_hour), 1),
            "points": [[p["latitude"], p["longitude"]] for p in member_points],
            "fir_ids": [p.get("fir_id") for p in member_points if p.get("fir_id") is not None],
        })

    return {"clusters": clusters, "outliers": outliers}
