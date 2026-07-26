try:
    import numpy as np
    from scipy.stats import gaussian_kde
    _HAS_KDE = True
except ImportError:
    _HAS_KDE = False


def compute_kde_heatmap(points, grid_size=40, padding_deg=0.01):
    """
    Fits a Gaussian Kernel Density Estimate over incident coordinates and evaluates it
    on a regular grid, producing a real density surface rather than plotting raw pins
    or DBSCAN cluster centroids as a proxy for "hot".

    points: list of [lat, lng] pairs
    Returns: {"grid": [{lat, lng, intensity}], "bandwidth": float} with intensity in [0, 1].
    Falls back to per-point unit intensity when there are too few/degenerate points to
    fit a KDE (e.g. all points identical, or fewer than 2 points).
    """
    if not _HAS_KDE or len(points) < 2:
        return {
            "grid": [{"lat": p[0], "lng": p[1], "intensity": 1.0} for p in points],
            "bandwidth": None,
            "method": "raw_points",
        }

    coords = np.array(points)
    lats, lngs = coords[:, 0], coords[:, 1]

    if np.ptp(lats) < 1e-9 and np.ptp(lngs) < 1e-9:
        # All incidents at (near) the same spot — KDE bandwidth would be degenerate.
        return {
            "grid": [{"lat": float(lats[0]), "lng": float(lngs[0]), "intensity": 1.0}],
            "bandwidth": None,
            "method": "raw_points",
        }

    try:
        kde = gaussian_kde(np.vstack([lats, lngs]))
    except np.linalg.LinAlgError:
        return {
            "grid": [{"lat": p[0], "lng": p[1], "intensity": 1.0} for p in points],
            "bandwidth": None,
            "method": "raw_points",
        }

    lat_min, lat_max = lats.min() - padding_deg, lats.max() + padding_deg
    lng_min, lng_max = lngs.min() - padding_deg, lngs.max() + padding_deg

    lat_grid = np.linspace(lat_min, lat_max, grid_size)
    lng_grid = np.linspace(lng_min, lng_max, grid_size)
    mesh_lat, mesh_lng = np.meshgrid(lat_grid, lng_grid)

    grid_coords = np.vstack([mesh_lat.ravel(), mesh_lng.ravel()])
    density = kde(grid_coords)

    max_density = density.max()
    if max_density > 0:
        density = density / max_density

    # Drop near-zero cells so the payload stays small and the heat layer isn't diluted
    # by a sea of negligible-intensity points.
    threshold = 0.05
    grid_points = [
        {"lat": float(mesh_lat.ravel()[i]), "lng": float(mesh_lng.ravel()[i]), "intensity": float(density[i])}
        for i in range(len(density))
        if density[i] >= threshold
    ]

    return {
        "grid": grid_points,
        "bandwidth": float(kde.factor),
        "method": "gaussian_kde",
    }
