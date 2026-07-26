import numpy as np
from PIL import Image

def feather_edges_only():
    input_path = "frontend/public/karnataka_emblem.jpg"
    output_path = "frontend/public/karnataka_emblem_feathered.png"

    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    h, w, _ = arr.shape

    # Normalized coordinates [-1, 1]
    y = np.linspace(-1.0, 1.0, h)
    x = np.linspace(-1.0, 1.0, w)
    xx, yy = np.meshgrid(x, y)

    # Calculate distance to rectangle boundary: max(|x|, |y|)
    edge_dist = np.maximum(np.abs(xx), np.abs(yy))

    # Keep inner 70% 100% opaque, feather outer 30% smoothly to 0 alpha
    inner_boundary = 0.65
    outer_boundary = 0.95

    alpha = np.ones((h, w), dtype=np.float32)
    feather_zone = (edge_dist > inner_boundary)

    # Smooth cosine fade from 1.0 at inner_boundary down to 0.0 at outer_boundary
    t = np.clip((edge_dist[feather_zone] - inner_boundary) / (outer_boundary - inner_boundary), 0.0, 1.0)
    alpha[feather_zone] = 0.5 * (1.0 + np.cos(np.pi * t))

    arr[:, :, 3] = alpha * 255.0

    result = Image.fromarray(arr.astype(np.uint8), "RGBA")
    result.save(output_path, "PNG")
    print(f"Feathered rectangular edges only! Output saved to {output_path}")

if __name__ == "__main__":
    feather_edges_only()
