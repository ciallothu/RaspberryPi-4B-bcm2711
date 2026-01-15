import os

from PIL import Image, ImageDraw, ImageOps

from app.models import Snapshot
from app.ui.fonts import load_font
from app.ui.ticker_display import Ticker
from app.ui.video.player import VideoPlayer
from app.ui.weather.icons import ICON_MAP


def status_bar(draw: ImageDraw.ImageDraw, snap: Snapshot, font, display_cfg: dict):
    w = display_cfg["w"]
    net = "OK" if snap.online else "OFF"
    wflag = "W" if (snap.weather.now.ok and not snap.weather.now.stale) else "w"
    s = f"NET:{net}  {wflag}  IP:{snap.ip}"
    draw.text((6, 4), s, font=font, fill=(255, 255, 255))
    # right side temp/load
    s2 = f"T:{snap.cpu_temp} L:{snap.load1}"
    tw = draw.textlength(s2, font=font)
    draw.text((w - tw - 6, 4), s2, font=font, fill=(255, 255, 255))


def render_clock_page(
    snap: Snapshot,
    ticker: Ticker,
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
    if snap.weather.now.ok:
        wline = f"{snap.weather.now.location_name} {snap.weather.now.temp_c}° {snap.weather.now.text}"
        if snap.weather.now.stale:
            wline += " ~"
        draw.text((12, 148), wline[:22], font=font_mid, fill=(255, 255, 255))
    else:
        draw.text((12, 148), "Weather: -", font=font_mid, fill=(255, 255, 255))

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
    icon_code = snap.weather.now.icon
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

    if snap.weather.now.ok:
        draw.text((10, 80), f"{snap.weather.now.location_name}", font=font_mid, fill=(255, 255, 255))
        draw.text((10, 130), f"{snap.weather.now.temp_c}°", font=font_big, fill=(255, 255, 255))
        draw.text((120, 146), f"{snap.weather.now.text}", font=font_mid, fill=(255, 255, 255))

        meta = f"obs:{snap.weather.now.obs_time[-14:]} upd:{snap.weather.now.update_time[-14:]}"
        if snap.weather.now.stale:
            meta = "STALE " + meta
        draw.text((10, 210), meta[:32], font=font_small, fill=(255, 255, 255))
        if snap.weather.now.err:
            draw.text((10, 230), f"err:{snap.weather.now.err}"[:32], font=font_small, fill=(255, 255, 255))
    else:
        draw.text((10, 120), "Weather unavailable", font=font_mid, fill=(255, 255, 255))
        if snap.weather.now.err:
            draw.text((10, 150), f"{snap.weather.now.err}"[:32], font=font_small, fill=(255, 255, 255))

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

    if snap.weather.now.ok:
        draw.text((10, y + 10), f"W: {snap.weather.now.temp_c}° {snap.weather.now.text}" + (" ~" if snap.weather.now.stale else ""),
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
        img = Image.new("RGB", (w, h), (0, 0, 0))
        fw, fh = frame.size
        if fw > 0 and fh > 0:
            scale = w / fw
            target = (max(1, int(fw * scale)), max(1, int(fh * scale)))
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.LANCZOS
            fitted = frame.resize(target, resample=resample)
            x = (w - target[0]) // 2
            y = (h - target[1]) // 2
            img.paste(fitted, (x, y))
            if target[1] < h:
                img.paste(fitted, (x, y - target[1]))
                img.paste(fitted, (x, y + target[1]))
    return img


def render_quote_page(snap: Snapshot, ticker: Ticker, display_cfg: dict) -> Image.Image:
    w, h = display_cfg["w"], display_cfg["h"]
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_mid = load_font(22)
    text = ticker.text
    if not text:
        text = "No quotes yet."
    max_width = w - 20
    words = text.split()
    lines = []
    current = ""
    for word in words:
        tentative = f"{current} {word}".strip()
        if draw.textlength(tentative, font=font_mid) <= max_width:
            current = tentative
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    total_height = len(lines) * 28
    y = max(10, (h - total_height) // 2)
    for line in lines:
        line_width = draw.textlength(line, font=font_mid)
        x = (w - line_width) // 2
        draw.text((x, y), line, font=font_mid, fill=(255, 255, 255))
        y += 28
    return img


def render_weekly_weather_page(snap: Snapshot, ticker: Ticker, display_cfg: dict) -> Image.Image:
    w, h = display_cfg["w"], display_cfg["h"]
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_small = load_font(14)
    font_mid = load_font(20)
    status_bar(draw, snap, font_small, display_cfg)

    draw.text((10, 36), "7-DAY FORECAST", font=font_mid, fill=(255, 255, 255))

    daily = snap.weather.daily[:7]
    start_y = 70
    row_h = 24
    for idx, day in enumerate(daily):
        y = start_y + idx * row_h
        date_label = day.date[5:] if len(day.date) >= 5 else day.date
        temp_label = f"{day.temp_min}~{day.temp_max}°"
        draw.text((10, y), date_label, font=font_small, fill=(255, 255, 255))
        draw.text((90, y), day.text_day[:10], font=font_small, fill=(255, 255, 255))
        temp_w = draw.textlength(temp_label, font=font_small)
        draw.text((w - temp_w - 10, y), temp_label, font=font_small, fill=(255, 255, 255))

    ticker.draw(img, font_small)
    return img


def render_dashboard_page(snap: Snapshot, ticker: Ticker, display_cfg: dict) -> Image.Image:
    w, h = display_cfg["w"], display_cfg["h"]
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_small = load_font(14)
    font_mid = load_font(20)
    font_big = load_font(40)

    status_bar(draw, snap, font_small, display_cfg)

    time_str = snap.now.strftime("%H:%M")
    date_str = snap.now.strftime("%Y-%m-%d")
    draw.text((10, 36), time_str, font=font_big, fill=(255, 255, 255))
    draw.text((10, 80), date_str, font=font_mid, fill=(255, 255, 255))

    weather_line = "Weather: -"
    if snap.weather.now.ok:
        weather_line = f"{snap.weather.now.location_name} {snap.weather.now.temp_c}° {snap.weather.now.text}"
        if snap.weather.now.stale:
            weather_line += " ~"
    draw.text((10, 110), weather_line[:28], font=font_mid, fill=(255, 255, 255))

    stats = [
        f"CPU: {snap.cpu_temp} ({snap.cpu_percent:.0f}%)",
        f"GPU: {snap.gpu_temp}",
        f"MEM: {snap.mem_percent:.0f}%",
        f"DISK: {snap.disk_percent:.0f}%",
        f"IP: {snap.ip}",
    ]
    y = 150
    for line in stats:
        draw.text((10, y), line, font=font_small, fill=(255, 255, 255))
        y += 20

    ticker.draw(img, font_small)
    return img


def render_lunar_page(snap: Snapshot, ticker: Ticker, display_cfg: dict) -> Image.Image:
    w, h = display_cfg["w"], display_cfg["h"]
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_small = load_font(14)
    font_mid = load_font(20)

    status_bar(draw, snap, font_small, display_cfg)
    draw.text((10, 36), "LUNAR", font=font_mid, fill=(255, 255, 255))

    lunar = snap.lunar
    if lunar is None:
        draw.text((10, 90), "Lunar data unavailable", font=font_mid, fill=(255, 255, 255))
        ticker.draw(img, font_small)
        return img

    lines = [
        f"Solar: {lunar.solar} {lunar.week}",
        f"Lunar: {lunar.lunar}",
        f"Ganzhi: {lunar.ganzhi_year}/{lunar.ganzhi_month}/{lunar.ganzhi_day}",
        f"Constellation: {lunar.constellation}",
        f"Yi: {lunar.yi}",
        f"Ji: {lunar.ji}",
    ]
    y = 70
    for line in lines:
        draw.text((10, y), line[:28], font=font_small, fill=(255, 255, 255))
        y += 24

    ticker.draw(img, font_small)
    return img
