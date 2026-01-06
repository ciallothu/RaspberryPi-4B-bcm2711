# app/ui/sprite.py
import os
from PIL import Image

class Sprite:
    """
    Load RGBA PNG frames from a folder and cycle at fps.
    """
    def __init__(self, folder: str, fps: int = 8):
        self.folder = folder
        self.fps = max(1, int(fps))
        self.frames: list[Image.Image] = []
        self.idx = 0
        self.last_ts = 0.0

        self._load_frames()

    def _load_frames(self) -> None:
        if not os.path.isdir(self.folder):
            return

        files = sorted([f for f in os.listdir(self.folder) if f.lower().endswith(".png")])
        for f in files:
            p = os.path.join(self.folder, f)
            try:
                self.frames.append(Image.open(p).convert("RGBA"))
            except Exception:
                continue

    def frame(self, now_ts: float) -> Image.Image | None:
        if not self.frames:
            return None

        if self.last_ts == 0.0:
            self.last_ts = now_ts
            return self.frames[self.idx]

        interval = 1.0 / self.fps
        if now_ts - self.last_ts >= interval:
            self.idx = (self.idx + 1) % len(self.frames)
            self.last_ts = now_ts

        return self.frames[self.idx]
