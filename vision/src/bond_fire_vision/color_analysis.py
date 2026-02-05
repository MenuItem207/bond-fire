"""Color analysis for person tracking.

Extracts dominant shirt colors from bounding boxes and maps RGB values
to human-readable color names.
"""

from __future__ import annotations

import colorsys
from typing import Any, Tuple

import cv2
import numpy as np


# CSS color name dictionary (140 colors)
CSS_COLORS = {
    "AliceBlue": (240, 248, 255),
    "AntiqueWhite": (250, 235, 215),
    "Aqua": (0, 255, 255),
    "Aquamarine": (127, 255, 212),
    "Azure": (240, 255, 255),
    "Beige": (245, 245, 220),
    "Bisque": (255, 228, 196),
    "Black": (0, 0, 0),
    "BlanchedAlmond": (255, 235, 205),
    "Blue": (0, 0, 255),
    "BlueViolet": (138, 43, 226),
    "Brown": (165, 42, 42),
    "BurlyWood": (222, 184, 135),
    "CadetBlue": (95, 158, 160),
    "Chartreuse": (127, 255, 0),
    "Chocolate": (210, 105, 30),
    "Coral": (255, 127, 80),
    "CornflowerBlue": (100, 149, 237),
    "Cornsilk": (255, 248, 220),
    "Crimson": (220, 20, 60),
    "Cyan": (0, 255, 255),
    "DarkBlue": (0, 0, 139),
    "DarkCyan": (0, 139, 139),
    "DarkGoldenRod": (184, 134, 11),
    "DarkGray": (169, 169, 169),
    "DarkGreen": (0, 100, 0),
    "DarkKhaki": (189, 183, 107),
    "DarkMagenta": (139, 0, 139),
    "DarkOliveGreen": (85, 107, 47),
    "DarkOrange": (255, 140, 0),
    "DarkOrchid": (153, 50, 204),
    "DarkRed": (139, 0, 0),
    "DarkSalmon": (233, 150, 122),
    "DarkSeaGreen": (143, 188, 143),
    "DarkSlateBlue": (72, 61, 139),
    "DarkSlateGray": (47, 79, 79),
    "DarkTurquoise": (0, 206, 209),
    "DarkViolet": (148, 0, 211),
    "DeepPink": (255, 20, 147),
    "DeepSkyBlue": (0, 191, 255),
    "DimGray": (105, 105, 105),
    "DodgerBlue": (30, 144, 255),
    "FireBrick": (178, 34, 34),
    "FloralWhite": (255, 250, 240),
    "ForestGreen": (34, 139, 34),
    "Fuchsia": (255, 0, 255),
    "Gainsboro": (220, 220, 220),
    "GhostWhite": (248, 248, 255),
    "Gold": (255, 215, 0),
    "GoldenRod": (218, 165, 32),
    "Gray": (128, 128, 128),
    "Green": (0, 128, 0),
    "GreenYellow": (173, 255, 47),
    "HoneyDew": (240, 255, 240),
    "HotPink": (255, 105, 180),
    "IndianRed": (205, 92, 92),
    "Indigo": (75, 0, 130),
    "Ivory": (255, 255, 240),
    "Khaki": (240, 230, 140),
    "Lavender": (230, 230, 250),
    "LavenderBlush": (255, 240, 245),
    "LawnGreen": (124, 252, 0),
    "LemonChiffon": (255, 250, 205),
    "LightBlue": (173, 216, 230),
    "LightCoral": (240, 128, 128),
    "LightCyan": (224, 255, 255),
    "LightGoldenRodYellow": (250, 250, 210),
    "LightGray": (211, 211, 211),
    "LightGreen": (144, 238, 144),
    "LightPink": (255, 182, 193),
    "LightSalmon": (255, 160, 122),
    "LightSeaGreen": (32, 178, 170),
    "LightSkyBlue": (135, 206, 250),
    "LightSlateGray": (119, 136, 153),
    "LightSteelBlue": (176, 196, 222),
    "LightYellow": (255, 255, 224),
    "Lime": (0, 255, 0),
    "LimeGreen": (50, 205, 50),
    "Linen": (250, 240, 230),
    "Magenta": (255, 0, 255),
    "Maroon": (128, 0, 0),
    "MediumAquaMarine": (102, 205, 170),
    "MediumBlue": (0, 0, 205),
    "MediumOrchid": (186, 85, 211),
    "MediumPurple": (147, 112, 219),
    "MediumSeaGreen": (60, 179, 113),
    "MediumSlateBlue": (123, 104, 238),
    "MediumSpringGreen": (0, 250, 154),
    "MediumTurquoise": (72, 209, 204),
    "MediumVioletRed": (199, 21, 133),
    "MidnightBlue": (25, 25, 112),
    "MintCream": (245, 255, 250),
    "MistyRose": (255, 228, 225),
    "Moccasin": (255, 228, 181),
    "NavajoWhite": (255, 222, 173),
    "Navy": (0, 0, 128),
    "OldLace": (253, 245, 230),
    "Olive": (128, 128, 0),
    "OliveDrab": (107, 142, 35),
    "Orange": (255, 165, 0),
    "OrangeRed": (255, 69, 0),
    "Orchid": (218, 112, 214),
    "PaleGoldenRod": (238, 232, 170),
    "PaleGreen": (152, 251, 152),
    "PaleTurquoise": (175, 238, 238),
    "PaleVioletRed": (219, 112, 147),
    "PapayaWhip": (255, 239, 213),
    "PeachPuff": (255, 218, 185),
    "Peru": (205, 133, 63),
    "Pink": (255, 192, 203),
    "Plum": (221, 160, 221),
    "PowderBlue": (176, 224, 230),
    "Purple": (128, 0, 128),
    "RebeccaPurple": (102, 51, 153),
    "Red": (255, 0, 0),
    "RosyBrown": (188, 143, 143),
    "RoyalBlue": (65, 105, 225),
    "SaddleBrown": (139, 69, 19),
    "Salmon": (250, 128, 114),
    "SandyBrown": (244, 164, 96),
    "SeaGreen": (46, 139, 87),
    "SeaShell": (255, 245, 238),
    "Sienna": (160, 82, 45),
    "Silver": (192, 192, 192),
    "SkyBlue": (135, 206, 235),
    "SlateBlue": (106, 90, 205),
    "SlateGray": (112, 128, 144),
    "Snow": (255, 250, 250),
    "SpringGreen": (0, 255, 127),
    "SteelBlue": (70, 130, 180),
    "Tan": (210, 180, 140),
    "Teal": (0, 128, 128),
    "Thistle": (216, 191, 216),
    "Tomato": (255, 99, 71),
    "Turquoise": (64, 224, 208),
    "Violet": (238, 130, 238),
    "Wheat": (245, 222, 179),
    "White": (255, 255, 255),
    "WhiteSmoke": (245, 245, 245),
    "Yellow": (255, 255, 0),
    "YellowGreen": (154, 205, 50),
}


def extract_dominant_color(frame: Any, bbox: Tuple[float, float, float, float]) -> Tuple[int, int, int]:
    """
    Extract the dominant shirt color from a person's bounding box.

    Args:
        frame: OpenCV frame (BGR format)
        bbox: Bounding box as (x1, y1, x2, y2) in pixel coordinates

    Returns:
        RGB tuple (r, g, b) with values 0-255
    """
    x1, y1, x2, y2 = [int(v) for v in bbox]
    height, width = frame.shape[:2]

    # Clamp bbox to frame bounds
    x1 = max(0, min(x1, width - 1))
    x2 = max(x1 + 1, min(x2, width))
    y1 = max(0, min(y1, height - 1))
    y2 = max(y1 + 1, min(y2, height))

    # Extract middle 40% vertically (torso/chest area)
    box_height = y2 - y1
    torso_top = y1 + int(box_height * 0.3)
    torso_bottom = y1 + int(box_height * 0.7)

    # Crop to torso region
    torso = frame[torso_top:torso_bottom, x1:x2]

    if torso.size == 0:
        return (128, 128, 128)  # Default gray

    # Convert BGR to RGB
    torso_rgb = cv2.cvtColor(torso, cv2.COLOR_BGR2RGB)

    # Reshape for k-means
    pixels = torso_rgb.reshape(-1, 3).astype(np.float32)

    # Filter out very dark (shadows) and very bright (highlights) pixels
    brightness = pixels.mean(axis=1)
    mask = (brightness > 30) & (brightness < 225)
    filtered_pixels = pixels[mask]

    if len(filtered_pixels) < 10:
        # Not enough valid pixels, use all
        filtered_pixels = pixels

    # K-means clustering (k=3)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    k = min(3, len(filtered_pixels))
    _, labels, centers = cv2.kmeans(
        filtered_pixels,
        k,
        None,
        criteria,
        attempts=3,
        flags=cv2.KMEANS_PP_CENTERS,
    )

    # Find largest cluster
    unique, counts = np.unique(labels, return_counts=True)
    dominant_idx = unique[np.argmax(counts)]
    dominant_color = centers[dominant_idx]

    # Round and convert to int
    r, g, b = [int(round(v)) for v in dominant_color]
    return (r, g, b)


def get_color_name(rgb: Tuple[int, int, int]) -> str:
    """
    Map an RGB value to a human-readable color name.

    Args:
        rgb: Tuple of (r, g, b) values 0-255

    Returns:
        Color name string (e.g., "Burnt Orange", "Steel Blue")
    """
    r, g, b = rgb

    # Convert to HSL for saturation/lightness analysis
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    saturation = s * 100
    lightness = l * 100

    # Low saturation = grayscale
    if saturation < 15:
        if lightness < 20:
            return "Black"
        elif lightness > 85:
            return "White"
        elif lightness > 60:
            return "Light Gray"
        elif lightness > 40:
            return "Gray"
        else:
            return "Dark Gray"

    # Find nearest CSS color
    min_distance = float("inf")
    closest_name = "Gray"

    for name, (cr, cg, cb) in CSS_COLORS.items():
        # Euclidean distance in RGB space
        distance = ((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2) ** 0.5
        if distance < min_distance:
            min_distance = distance
            closest_name = name

    # Add descriptive prefix for very bright/dark variants
    if lightness < 25 and "Dark" not in closest_name and closest_name not in {"Black", "Navy", "Maroon"}:
        closest_name = f"Dark {closest_name}"
    elif lightness > 80 and "Light" not in closest_name and closest_name not in {"White", "Snow", "Ivory"}:
        closest_name = f"Light {closest_name}"

    return closest_name


def get_palette_from_people(people_colors: list[Tuple[int, int, int]], max_colors: int = 4) -> list[int]:
    """
    Create a flattened RGB palette from multiple people's shirt colors.

    Args:
        people_colors: List of RGB tuples
        max_colors: Maximum number of colors in palette

    Returns:
        Flattened list of RGB values [r1,g1,b1,r2,g2,b2,...]
    """
    if not people_colors:
        return [255, 100, 0]  # Default fire orange

    # Deduplicate similar colors (within 30 units)
    unique_colors = []
    for color in people_colors[:max_colors]:
        is_unique = True
        for existing in unique_colors:
            distance = sum((a - b) ** 2 for a, b in zip(color, existing)) ** 0.5
            if distance < 30:
                is_unique = False
                break
        if is_unique:
            unique_colors.append(color)

    # Flatten to [r,g,b,r,g,b,...]
    palette = []
    for r, g, b in unique_colors[:max_colors]:
        palette.extend([r, g, b])

    return palette


def color_distance(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
    """
    Calculate perceptual color distance between two RGB colors.

    Uses simplified Euclidean distance in RGB space.

    Args:
        rgb1: First RGB tuple
        rgb2: Second RGB tuple

    Returns:
        Distance value (0 = identical, ~441 = max difference)
    """
    return sum((a - b) ** 2 for a, b in zip(rgb1, rgb2)) ** 0.5


def are_colors_contrasting(
    rgb1: Tuple[int, int, int],
    rgb2: Tuple[int, int, int],
    threshold: float = 100.0,
) -> bool:
    """
    Check if two colors are sufficiently contrasting for visual interest.

    Args:
        rgb1: First RGB tuple
        rgb2: Second RGB tuple
        threshold: Minimum distance to be considered contrasting (default 100)

    Returns:
        True if colors are contrasting
    """
    return color_distance(rgb1, rgb2) > threshold
