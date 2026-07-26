import numpy as np
from PIL import Image, ImageFilter

def process_emblem():
    input_path = "frontend/public/karnataka_emblem.jpg"
    output_path = "frontend/public/karnataka_emblem_clean.png"

    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img, dtype=np.float32)

    r, g, b, _ = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

    # Calculate luminance / brightness of each pixel
    luminance = 0.299 * r + 0.587 * g + 0.114 * b

    # Estimate background color from outer corners
    h, w, _ = arr.shape
    corner_bg = np.mean([
        arr[:30, :30, :3],
        arr[:30, -30:, :3],
        arr[-30:, :30, :3],
        arr[-30:, -30:, :3]
    ], axis=(0, 1, 2))

    # Color difference from background
    color_diff = np.sqrt(
        (r - corner_bg[0])**2 + 
        (g - corner_bg[1])**2 + 
        (b - corner_bg[2])**2
    )

    # Combined feature for foreground mask
    bg_threshold = 28.0
    fg_strength = np.clip((color_diff - bg_threshold) / 40.0, 0.0, 1.0)
    lum_strength = np.clip((luminance - 25.0) / 45.0, 0.0, 1.0)
    
    alpha = np.maximum(fg_strength, lum_strength)

    # Apply radial vignette mask to guarantee ZERO rectangular border near edges
    y_coords, x_coords = np.ogrid[:h, :w]
    center_y, center_x = h / 2.0, w / 2.0
    radius = min(h, w) * 0.46

    dist_from_center = np.sqrt((x_coords - center_x)**2 + (y_coords - center_y)**2)
    radial_mask = np.clip(1.0 - (dist_from_center - (radius * 0.55)) / (radius * 0.45), 0.0, 1.0)
    # Smooth radial curve
    radial_mask = radial_mask * radial_mask * (3.0 - 2.0 * radial_mask)

    final_alpha = alpha * radial_mask
    final_alpha = np.clip(final_alpha * 255.0, 0.0, 255.0).astype(np.uint8)

    # Set new alpha channel
    arr[:, :, 3] = final_alpha

    # Convert back to PIL Image and apply subtle edge softening
    result = Image.fromarray(arr.astype(np.uint8), "RGBA")
    
    # Save crisp transparent PNG
    result.save(output_path, "PNG")
    print(f"Successfully processed {input_path} -> {output_path} with pristine transparent blending!")

if __name__ == "__main__":
    process_emblem()
