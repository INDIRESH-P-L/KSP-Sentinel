import numpy as np
from PIL import Image

def feather_rectangular_mask():
    input_path = "frontend/public/karnataka_emblem.jpg"
    output_path = "frontend/public/karnataka_emblem.png"

    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    h, w, _ = arr.shape

    # Normalize coordinates to [-1, 1] relative to center
    y = np.linspace(-1.0, 1.0, h)
    x = np.linspace(-1.0, 1.0, w)
    xx, yy = np.meshgrid(x, y)

    # Super-elliptical distance for natural rounded edge feathering
    radius = np.power(np.abs(xx)**2.8 + np.abs(yy)**2.8, 1.0 / 2.8)

    inner_r = 0.62
    outer_r = 0.94

    alpha = np.ones((h, w), dtype=np.float32)
    feather_mask = (radius > inner_r)

    t = np.clip((radius[feather_mask] - inner_r) / (outer_r - inner_r), 0.0, 1.0)
    # Smooth cosine falloff
    alpha[feather_mask] = 0.5 * (1.0 + np.cos(np.pi * t))

    arr[:, :, 3] = alpha * 255.0

    result = Image.fromarray(arr.astype(np.uint8), "RGBA")
    result.save(output_path, "PNG")
    print(f"Created smooth feathered emblem PNG: {output_path}")

if __name__ == "__main__":
    feather_rectangular_mask()
