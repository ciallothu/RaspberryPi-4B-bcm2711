# RaspberryPi-4B-bcm2711

## Video playback (frame-based)

This project plays video by cycling pre-rendered image frames and drawing them to the SPI LCD.

### Prepare frames on a server (16:9 → 320x240 landscape)

Generate frames with the `video_00001.jpg` naming pattern and place them under
`app/ui/pictures`. Subfolders are supported (e.g. `app/ui/pictures/SongofPhaethon`). The
player loads `video_*.jpg/png/jpeg` recursively.

Example (center-crop to 320x240 at 10 fps):

```bash
ffmpeg -i input.mp4 \
  -vf "scale=320:240:force_original_aspect_ratio=increase,crop=320:240,fps=10" \
  app/ui/pictures/SongofPhaethon/video_%05d.jpg
```

The video page appears automatically when frames are present. Adjust playback speed with
`display.fps_video` in `app/config.yaml`.

### Fonts

Place `arialbd.ttf` in `app/ui/fonts/arialbd.ttf` to use the preferred font.
