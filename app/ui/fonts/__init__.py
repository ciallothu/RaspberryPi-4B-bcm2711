import os
from PIL import ImageFont


def load_font(size: int) -> ImageFont.ImageFont:
    # Prefer the font shipped in the driver zip (arialbd.ttf)
    base = os.path.dirname(__file__)
    app_root = os.path.dirname(os.path.dirname(base))
    candidates = [
        os.path.join(base, "arialbd.ttf"),
        os.path.join(app_root, "drivers", "fonts", "arialbd.ttf"),
        os.path.join(app_root, "fonts", "arialbd.ttf"),
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
