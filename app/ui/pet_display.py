import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from PIL import ImageDraw

from app.ui.sprite import Sprite


@dataclass
class PetSprites:
    normal: Optional[Sprite]
    alert: Optional[Sprite]


class PetRenderer:
    def __init__(self, sprites: PetSprites):
        self.sprites = sprites

    def render(self, img, draw: ImageDraw.ImageDraw, pos: Tuple[int, int], online: bool, alert: bool) -> None:
        sprite = self.sprites.alert if alert else self.sprites.normal
        frame = sprite.frame(time.time()) if sprite is not None else None
        if frame is not None:
            img.paste(frame, pos, frame)
            return
        self._draw_fallback(draw, pos[0], pos[1], online=online, alert=alert)

    @staticmethod
    def _draw_fallback(draw: ImageDraw.ImageDraw, x: int, y: int, online: bool, alert: bool) -> None:
        w, h = 72, 72
        draw.rectangle([x, y, x + w, y + h], outline=(255, 255, 255), width=2)

        if alert:
            # angry / alert face
            draw.line([x+16, y+24, x+30, y+28], fill=(255, 255, 255), width=2)
            draw.line([x+44, y+28, x+58, y+24], fill=(255, 255, 255), width=2)
            draw.rectangle([x+20, y+30, x+26, y+36], fill=(255, 255, 255))
            draw.rectangle([x+46, y+30, x+52, y+36], fill=(255, 255, 255))
            draw.arc([x+20, y+44, x+52, y+66], start=200, end=340, fill=(255, 255, 255), width=2)
            return

        if online:
            draw.rectangle([x+18, y+24, x+26, y+32], fill=(255, 255, 255))
            draw.rectangle([x+46, y+24, x+54, y+32], fill=(255, 255, 255))
            draw.arc([x+18, y+34, x+54, y+62], start=10, end=170, fill=(255, 255, 255), width=2)
        else:
            draw.line([x+18, y+24, x+28, y+34], fill=(255, 255, 255), width=2)
            draw.line([x+28, y+24, x+18, y+34], fill=(255, 255, 255), width=2)
            draw.line([x+46, y+24, x+56, y+34], fill=(255, 255, 255), width=2)
            draw.line([x+56, y+24, x+46, y+34], fill=(255, 255, 255), width=2)
            draw.line([x+22, y+54, x+50, y+54], fill=(255, 255, 255), width=2)


def load_pet_sprites(base_dir: str, fps: int) -> PetSprites:
    """Create pet sprites from assets directory if available."""
    def _load(folder: str) -> Optional[Sprite]:
        if not os.path.isdir(folder):
            return None
        sprite = Sprite(folder, fps=fps)
        return sprite if sprite.frames else None

    normal_dir = os.path.join(base_dir, "normal")
    alert_dir = os.path.join(base_dir, "alert")

    normal = _load(normal_dir)
    alert = _load(alert_dir)

    if normal is None and alert is None:
        print("[deskpet] sprite assets missing; using fallback drawing.")

    return PetSprites(normal=normal, alert=alert)
