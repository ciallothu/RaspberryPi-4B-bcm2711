import os
from PIL import ImageFont


def load_font(size: int) -> ImageFont.ImageFont:
    # Prefer the font shipped in the driver zip (arialbd.ttf)
    base = os.path.dirname(__file__)
    candidates = [
        os.path.join(os.path.dirname(base), "drivers", "fonts", "arialbd.ttf"),
        os.path.join(base, "assets", "fonts", "arialbd.ttf"),
        os.path.join(os.path.dirname(base), "fonts", "arialbd.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()
