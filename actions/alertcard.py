from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from actions.levels import (
    RISK_ENGLISH_ACTION,
    RISK_HEX,
    RISK_NEPALI,
    RISK_NEPALI_ACTION,
    RiskLevel,
    coerce_level,
)
from analysis.render.floodmap import compose_rgb, crop_to_flood, load_flood_raster, lonlat_to_pixel
from core.config import paths
from core.corridor import Corridor

CARD_WIDTH = 1080
CARD_HEIGHT = 1920
HEADER_HEIGHT = 300
MAP_TOP = HEADER_HEIGHT
MAP_HEIGHT = 1120
INFO_TOP = MAP_TOP + MAP_HEIGHT
FLOOD_WIDEN_PX = 5
OUTSIDE_DOMAIN = (26, 28, 33)

DEVANAGARI_FONT = Path("/usr/share/fonts/noto/NotoSansDevanagari-Bold.ttf")
DEVANAGARI_REGULAR = Path("/usr/share/fonts/noto/NotoSansDevanagari-Regular.ttf")
LATIN_DIR = Path(matplotlib.__file__).resolve().parent / "mpl-data" / "fonts" / "ttf"
LATIN_BOLD = LATIN_DIR / "DejaVuSans-Bold.ttf"
LATIN_REGULAR = LATIN_DIR / "DejaVuSans.ttf"

INK = (245, 247, 250)
MUTED = (168, 178, 192)
PANEL = (16, 19, 24)


@dataclass(frozen=True)
class AlertCard:
    path: Path
    settlement: str
    level: RiskLevel
    replay: bool


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    raw = value.lstrip("#")
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


@dataclass(frozen=True)
class MapFrame:
    image: Image.Image
    scale: float
    offset_x: float
    offset_y: float


def _frame_map(rgb: np.ndarray, focus: tuple[int, int]) -> MapFrame:
    image = Image.fromarray(rgb)
    scale = max(CARD_WIDTH / image.width, MAP_HEIGHT / image.height)
    resized = image.resize(
        (max(CARD_WIDTH, round(image.width * scale)), max(MAP_HEIGHT, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = _clamp(focus[1] * scale - CARD_WIDTH / 2, 0.0, resized.width - CARD_WIDTH)
    top = _clamp(focus[0] * scale - MAP_HEIGHT / 2, 0.0, resized.height - MAP_HEIGHT)
    canvas = Image.new("RGB", (CARD_WIDTH, MAP_HEIGHT), OUTSIDE_DOMAIN)
    canvas.paste(resized, (-int(left), -int(top)))
    return MapFrame(canvas, scale, float(int(left)), float(int(top)))


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), max(low, high))


def _place(frame: MapFrame, points: dict[str, tuple[int, int]]) -> dict[str, tuple[int, int]]:
    placed: dict[str, tuple[int, int]] = {}
    for name, (row, col) in points.items():
        x = col * frame.scale - frame.offset_x
        y = row * frame.scale - frame.offset_y
        if -30 <= x <= CARD_WIDTH + 30 and -30 <= y <= MAP_HEIGHT + 30:
            placed[name] = (int(round(x)), int(round(y)))
    return placed


def _draw_runs(
    draw: ImageDraw.ImageDraw,
    origin: tuple[int, int],
    runs: list[tuple[str, ImageFont.FreeTypeFont]],
    fill: tuple[int, int, int],
) -> None:
    cursor, baseline = origin
    for text, font in runs:
        draw.text((cursor, baseline), text, font=font, fill=fill, anchor="ls")
        cursor += int(draw.textlength(text, font=font))


def _draw_header(
    draw: ImageDraw.ImageDraw, level: RiskLevel, settlement: str, replay: bool
) -> None:
    colour = _hex_to_rgb(RISK_HEX[level])
    draw.rectangle([0, 0, CARD_WIDTH, HEADER_HEIGHT], fill=colour)
    _draw_runs(
        draw,
        (48, 72),
        [("SANKET ", _font(LATIN_BOLD, 34)), ("संकेत", _font(DEVANAGARI_FONT, 34))],
        INK,
    )
    draw.text((48, 100), level, font=_font(LATIN_BOLD, 92), fill=INK)
    draw.text((48, 204), RISK_NEPALI[level], font=_font(DEVANAGARI_FONT, 64), fill=INK)
    label = _font(LATIN_BOLD, 40)
    right = CARD_WIDTH - 48
    draw.text((right, 104), settlement, font=label, fill=INK, anchor="ra")
    if replay:
        draw.text((right, 158), "REPLAY - TEST", font=_font(LATIN_BOLD, 30), fill=INK, anchor="ra")


def _draw_markers(
    canvas: Image.Image, placed: dict[str, tuple[int, int]], highlight: str
) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    for name, (x, y) in placed.items():
        target = name == highlight
        radius = 16 if target else 9
        fill = (255, 255, 255, 255) if target else (210, 220, 235, 210)
        draw.ellipse([x - radius - 4, y - radius - 4, x + radius + 4, y + radius + 4],
                     fill=(8, 12, 20, 170))
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=fill)
        font = _font(LATIN_BOLD, 34 if target else 26)
        text_x = x + radius + 12
        anchor = "lm"
        if text_x > CARD_WIDTH - 240:
            text_x = x - radius - 12
            anchor = "rm"
        box = draw.textbbox((text_x, y), name, font=font, anchor=anchor)
        draw.rectangle([box[0] - 10, box[1] - 6, box[2] + 10, box[3] + 6], fill=(8, 12, 20, 190))
        draw.text((text_x, y), name, font=font, fill=INK, anchor=anchor)


def _draw_legend(canvas: Image.Image, max_depth_m: float) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    height = 96
    top = MAP_HEIGHT - height
    draw.rectangle([0, top, CARD_WIDTH, MAP_HEIGHT], fill=(8, 12, 20, 210))
    draw.text((48, top + 20), "Modelled flood path", font=_font(LATIN_BOLD, 30), fill=INK)
    draw.text((48, top + 60), "peak rise on the river network, line width symbolic",
              font=_font(LATIN_REGULAR, 22), fill=MUTED)
    bar_left = CARD_WIDTH - 400
    for index in range(300):
        shade = index / 299
        draw.rectangle(
            [bar_left + index, top + 30, bar_left + index + 1, top + 56],
            fill=(int(86 + shade * 104), int(180 - shade * 150), int(233 - shade * 137)),
        )
    draw.text((bar_left, top + 62), "0 m", font=_font(LATIN_REGULAR, 22), fill=MUTED)
    draw.text((bar_left + 300, top + 62), f"{max_depth_m:.1f} m",
              font=_font(LATIN_REGULAR, 22), fill=MUTED, anchor="ra")


def _wrap(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_info(
    draw: ImageDraw.ImageDraw,
    level: RiskLevel,
    lead_time_minutes: float | None,
    vintage: str,
    scenario: str,
) -> None:
    draw.rectangle([0, INFO_TOP, CARD_WIDTH, CARD_HEIGHT], fill=PANEL)
    y: float = INFO_TOP + 34
    if lead_time_minutes is not None:
        lead_font = _font(LATIN_BOLD, 76)
        lead_text = f"{lead_time_minutes:.0f} min"
        draw.text((48, int(y)), lead_text, font=lead_font, fill=INK)
        _draw_runs(
            draw,
            (48 + int(draw.textlength(lead_text, font=lead_font)) + 24, int(y) + 62),
            [
                ("estimated arrival / ", _font(LATIN_REGULAR, 28)),
                ("अनुमानित समय", _font(DEVANAGARI_REGULAR, 28)),
            ],
            MUTED,
        )
        y += 112
    for text, font, fill in (
        (RISK_ENGLISH_ACTION[level], _font(LATIN_BOLD, 38), INK),
        (RISK_NEPALI_ACTION[level], _font(DEVANAGARI_FONT, 40), INK),
    ):
        for line in _wrap(draw, text, font, CARD_WIDTH - 96):
            draw.text((48, int(y)), line, font=font, fill=fill)
            y += font.size + 12
        y += 10
    footer = _font(LATIN_REGULAR, 22)
    draw.text((48, CARD_HEIGHT - 96), f"SCENARIO - not an observation - {scenario}",
              font=footer, fill=MUTED)
    draw.text((48, CARD_HEIGHT - 62),
              f"HMA 8 m DEM {vintage} - 1D Saint-Venant routing - SANKET",
              font=footer, fill=MUTED)


def _output_path(settlement: str, run_id: str) -> Path:
    paths.dist.mkdir(parents=True, exist_ok=True)
    directory = paths.dist / "alertcards"
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(f"{settlement}|{run_id}".encode()).hexdigest()[:12]
    return directory / f"alert_{digest}.png"


def render_alert_card(
    corridor: Corridor,
    settlement: str,
    level: str,
    run_id: str,
    *,
    lead_time_minutes: float | None = None,
    scenario_slug: str = "reference_v1.0_d30_full",
    replay: bool = False,
) -> AlertCard:
    resolved = coerce_level(level)
    raster = crop_to_flood(load_flood_raster(scenario_slug))
    rgb = compose_rgb(raster, widen_px=FLOOD_WIDEN_PX)
    points = {
        station.name: lonlat_to_pixel(raster, station.location[0], station.location[1])
        for station in corridor.downstream_reach
    }
    focus = points.get(settlement, (raster.depth_m.shape[0] // 2, raster.depth_m.shape[1] // 2))
    frame = _frame_map(rgb, focus)
    overlay = frame.image.convert("RGB")
    _draw_markers(overlay, _place(frame, points), settlement)
    _draw_legend(overlay, raster.max_depth_m)
    canvas = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), PANEL)
    canvas.paste(overlay, (0, MAP_TOP))
    draw = ImageDraw.Draw(canvas)
    _draw_header(draw, resolved, settlement, replay)
    _draw_info(draw, resolved, lead_time_minutes, corridor.dem_vintage.isoformat(), scenario_slug)
    target = _output_path(settlement, run_id)
    canvas.save(target, format="PNG", optimize=True)
    return AlertCard(path=target, settlement=settlement, level=resolved, replay=replay)
