import glob
import os
import time
from typing import List, Optional, Tuple

from PIL import Image


class VideoPlayer:
    def __init__(self, frames_dir: str, size: Tuple[int, int], fps: int = 10) -> None:
        self.frames_dir = frames_dir
        self.size = size
        self.fps = max(1, int(fps))
        self.frame_interval = 1.0 / self.fps
        self._frames: List[str] = []
        self._idx = 0
        self._last_ts = 0.0
        self._load_frames()

    def _load_frames(self) -> None:
        if not os.path.isdir(self.frames_dir):
            return
        patterns = ["video_*.jpg", "video_*.jpeg", "video_*.png"]
        frames: List[str] = []
        for pattern in patterns:
            frames.extend(glob.glob(os.path.join(self.frames_dir, pattern)))
        self._frames = sorted(frames)

    @property
    def available(self) -> bool:
        return bool(self._frames)

    def next_frame(self) -> Optional[Image.Image]:
        if not self._frames:
            return None

        now = time.monotonic()
        if self._last_ts and now - self._last_ts < self.frame_interval:
            # reuse current frame to honor FPS timing
            path = self._frames[self._idx]
        else:
            self._idx = (self._idx + 1) % len(self._frames)
            self._last_ts = now
            path = self._frames[self._idx]

        try:
            with Image.open(path) as img:
                frame = img.convert("RGB")
        except Exception:
            return None

        if frame.size != self.size:
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.LANCZOS
            frame = frame.resize(self.size, resample=resample)

        return frame
