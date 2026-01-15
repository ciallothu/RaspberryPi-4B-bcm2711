import time
from typing import Optional

from PIL import Image, ImageDraw, ImageFont


class Ticker:
    def __init__(self, height: int):
        self.offset = 0.0
        self.last_t = time.monotonic()
        self.text = "INIT"
        self._cached_width: Optional[float] = None
        self.height = height

    def set_text(self, text: str):
        if text != self.text:
            self.text = text
            self._cached_width = None
            self.offset = 0.0

    def step(self, speed_px_per_s: float):
        now = time.monotonic()
        dt = now - self.last_t
        self.last_t = now
        self.offset += speed_px_per_s * dt

    def draw(self, img: Image.Image, font: ImageFont.ImageFont):
        draw = ImageDraw.Draw(img)
        w, h = img.size
        y0 = h - self.height
        draw.rectangle([0, y0, w, h], fill=(0, 0, 0))

        # measure once
        if self._cached_width is None:
            self._cached_width = draw.textlength(self.text, font=font)

        gap = 30
        total = self._cached_width + gap
        if total <= 0:
            return

        # loop offset
        off = self.offset % total
        x = int(w - off)

        # draw repeated to cover whole line
        while x < w:
            draw.text((x, y0 + 6), self.text, font=font, fill=(255, 255, 255))
            x += int(total)
