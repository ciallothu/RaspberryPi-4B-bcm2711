import os

from PIL import Image, ImageDraw

from app.models import Snapshot
from app.ui.fonts import load_font
from app.ui.pet_display import PetRenderer
from app.ui.ticker_display import Ticker
from app.ui.video.player import VideoPlayer
from app.ui.weather.icons import ICON_MAP


def status_bar(draw: ImageDraw.ImageDraw, snap: Snapshot, font, display_cfg: dict):
    w = display_cfg["w"]
    net = "OK" if snap.online else "OFF"
    wflag = "W" if (snap.weather.ok and not snap.weather.stale) else "w"
    s = f"NET:{net}  {wflag}  IP:{snap.ip}"
    draw.text((6, 4), s, font=font, fill=(255, 255, 255))
    # right side temp/load
    s2 = f"T:{snap.cpu_temp} L:{snap.load1}"
    tw = draw.textlength(s2, font=font)
    draw.text((w - tw - 6, 4), s2, font=font, fill=(255, 255, 255))


def render_clock_page(
    snap: Snapshot,
    ticker: Ticker,
    pet_renderer: PetRenderer,
    display_cfg: dict,
) -> Image.Image:
    w, h = display_cfg["w"], display_cfg["h"]
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_small = load_font(14)
    font_mid = load_font(22)
    font_big = load_font(54)

    status_bar(draw, snap, font_small, display_cfg)

    # time
    t_str = snap.now.strftime("%H:%M")
    draw.text((10, 40), t_str, font=font_big, fill=(255, 255, 255))

    # date
    d_str = snap.now.strftime("%Y-%m-%d %a")
    draw.text((12, 110), d_str, font=font_mid, fill=(255, 255, 255))

    # quick weather hint
    if snap.weather.ok:
        wline = f"{snap.weather.location_name} {snap.weather.temp_c}° {snap.weather.text}"
        if snap.weather.stale:
            wline += " ~"
        draw.text((12, 148), wline[:22], font=font_mid, fill=(255, 255, 255))
    else:
        draw.text((12, 148), "Weather: -", font=font_mid, fill=(255, 255, 255))

    # ===== desk pet sprite =====
    alert_mode = (not snap.online) or (snap.weather.ok and snap.weather.stale)
    pet_renderer.render(img, draw, pos=(w - 90, h - 110), online=snap.online, alert=alert_mode)

    ticker.draw(img, font_small)
    return img


def render_weather_page(snap: Snapshot, ticker: Ticker, display_cfg: dict) -> Image.Image:
    w, h = display_cfg["w"], display_cfg["h"]
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_small = load_font(14)
    font_mid = load_font(22)
    font_big = load_font(48)

    status_bar(draw, snap, font_small, display_cfg)
    icon_code = snap.weather.icon
    icon_name = ICON_MAP.get(icon_code, "unknown.png")
    ui_root = os.path.dirname(os.path.dirname(__file__))
    icon_path = os.path.join(ui_root, "assets", "icons", icon_name)

    try:
        icon = Image.open(icon_path).convert("RGBA")
        # Put icon on left area
        img.paste(icon, (10, 90), icon)
    except Exception:
        pass
    title = "WEATHER"
    draw.text((10, 36), title, font=font_mid, fill=(255, 255, 255))

    if snap.weather.ok:
        draw.text((10, 80), f"{snap.weather.location_name}", font=font_mid, fill=(255, 255, 255))
        draw.text((10, 130), f"{snap.weather.temp_c}°", font=font_big, fill=(255, 255, 255))
        draw.text((120, 146), f"{snap.weather.text}", font=font_mid, fill=(255, 255, 255))

        meta = f"obs:{snap.weather.obs_time[-14:]} upd:{snap.weather.update_time[-14:]}"
        if snap.weather.stale:
            meta = "STALE " + meta
        draw.text((10, 210), meta[:32], font=font_small, fill=(255, 255, 255))
        if snap.weather.err:
            draw.text((10, 230), f"err:{snap.weather.err}"[:32], font=font_small, fill=(255, 255, 255))
    else:
        draw.text((10, 120), "Weather unavailable", font=font_mid, fill=(255, 255, 255))
        if snap.weather.err:
            draw.text((10, 150), f"{snap.weather.err}"[:32], font=font_small, fill=(255, 255, 255))

    ticker.draw(img, font_small)
    return img


def render_status_page(snap: Snapshot, ticker: Ticker, display_cfg: dict) -> Image.Image:
    w, h = display_cfg["w"], display_cfg["h"]
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_small = load_font(14)
    font_mid = load_font(22)

    status_bar(draw, snap, font_small, display_cfg)

    draw.text((10, 36), "STATUS", font=font_mid, fill=(255, 255, 255))

    lines = [
        f"CPU temp: {snap.cpu_temp}",
        f"Load1:    {snap.load1}",
        f"IP:       {snap.ip}",
        f"Network:  {'ONLINE' if snap.online else 'OFFLINE'}",
    ]
    y = 80
    for ln in lines:
        draw.text((10, y), ln, font=font_mid, fill=(255, 255, 255))
        y += 34

    if snap.weather.ok:
        draw.text((10, y + 10), f"W: {snap.weather.temp_c}° {snap.weather.text}" + (" ~" if snap.weather.stale else ""),
                  font=font_mid, fill=(255, 255, 255))

    ticker.draw(img, font_small)
    return img


def render_video_page(
    snap: Snapshot,
    ticker: Ticker,
    video_player: VideoPlayer,
    display_cfg: dict,
) -> Image.Image:
    w, h = display_cfg["w"], display_cfg["h"]
    frame = video_player.next_frame()
    if frame is None:
        img = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        font_mid = load_font(20)
        draw.text((10, 10), "No video frames.", font=font_mid, fill=(255, 255, 255))
    else:
        img = frame
    font_small = load_font(14)
    ticker.draw(img, font_small)
    return img
