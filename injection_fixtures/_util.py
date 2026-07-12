"""Shared rendering helpers used by both the injection techniques and the benign
control generators. Nothing here reaches the network or the filesystem.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

DEFAULT_SIZE: Tuple[int, int] = (600, 400)

# Caps on untrusted input (CLI text, consumer-supplied size). A single test
# fixture image has no business being huge, and an unbounded instruction
# string turned into single-character line-wraps would mean thousands of
# draw calls for no benefit.
MAX_TEXT_LEN = 500
MAX_DIMENSION = 10_000


def clip_text(text: str) -> str:
    """Cap and validate the instruction/caption text before it is rendered."""
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")
    return text[:MAX_TEXT_LEN]


def validate_size(size: Tuple[int, int]) -> Tuple[int, int]:
    """Coerce and bound-check a (width, height) pair, or raise ValueError."""
    try:
        w, h = size
        w, h = int(w), int(h)
    except (TypeError, ValueError):
        raise ValueError(f"size must be a (width, height) pair of ints, got {size!r}") from None
    if w <= 0 or h <= 0:
        raise ValueError(f"size must have positive width and height, got {(w, h)!r}")
    if w > MAX_DIMENSION or h > MAX_DIMENSION:
        raise ValueError(f"size must not exceed {MAX_DIMENSION} in either dimension, got {(w, h)!r}")
    return (w, h)


def load_font(size: int) -> ImageFont.ImageFont:
    """The bundled Pillow default font, scaled to `size` where supported."""
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Pillow older than 10.1 has no `size` argument on load_default.
        return ImageFont.load_default()


def line_height(font: ImageFont.ImageFont, default: int = 18) -> int:
    size = getattr(font, "size", None)
    if isinstance(size, (int, float)) and size > 0:
        return int(size * 1.35)
    return default


def canvas(size: Tuple[int, int], base_image: Optional[Image.Image], fill="white") -> Image.Image:
    """An RGBA canvas of `size`: `base_image` resized if given, else a flat fill."""
    if base_image is not None:
        return base_image.convert("RGBA").resize(size)
    return Image.new("RGBA", size, fill)


def noise_background(size: Tuple[int, int], sigma: int = 40) -> Image.Image:
    """A grayscale-noise 'photo-like' busy background, RGBA."""
    return Image.effect_noise(size, sigma).convert("RGBA")


def checkerboard(
    size: Tuple[int, int],
    cell: int = 4,
    colors: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = ((20, 20, 20), (235, 235, 235)),
) -> Image.Image:
    """A fine checkerboard: maximal edge density, used as a high-frequency region."""
    tile = Image.new("RGB", (cell * 2, cell * 2), colors[1])
    draw = ImageDraw.Draw(tile)
    draw.rectangle((0, 0, cell - 1, cell - 1), fill=colors[0])
    draw.rectangle((cell, cell, cell * 2 - 1, cell * 2 - 1), fill=colors[0])
    w, h = size
    img = Image.new("RGB", size)
    tw, th = tile.size
    for y in range(0, h, th):
        for x in range(0, w, tw):
            img.paste(tile, (x, y))
    return img.convert("RGBA")


def near_background_color(background_rgb: Tuple[int, int, int], delta: int) -> Tuple[int, int, int]:
    """A text color `delta` shades away from `background_rgb`, clamped to [0, 255].

    `delta=0` reproduces the background color exactly, i.e. invisible text.
    A small delta stays close to indistinguishable at a glance while still
    being a distinct pixel value.
    """
    return tuple(
        max(0, c - delta) if c >= 128 else min(255, c + delta)
        for c in background_rgb
    )


def _split_long_word(draw: ImageDraw.ImageDraw, word: str, font, max_width: int) -> List[str]:
    if draw.textlength(word, font=font) <= max_width:
        return [word]
    pieces: List[str] = []
    cur = ""
    for ch in word:
        trial = cur + ch
        if cur and draw.textlength(trial, font=font) > max_width:
            pieces.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        pieces.append(cur)
    return pieces


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> List[str]:
    """Word-wrap `text` to `max_width`, splitting mid-word if a single word
    (or a text string with no spaces at all) would otherwise overflow it.
    """
    max_width = max(1, max_width)
    words = text.split()
    if not words:
        return [""]
    lines: List[str] = []
    cur = ""
    for word in words:
        for piece in _split_long_word(draw, word, font, max_width):
            trial = f"{cur} {piece}".strip()
            if cur and draw.textlength(trial, font=font) > max_width:
                lines.append(cur)
                cur = piece
            else:
                cur = trial
    if cur:
        lines.append(cur)
    return lines
