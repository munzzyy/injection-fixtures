"""Shared rendering helpers used by both the injection techniques and the benign
control generators. Nothing here reaches the network or the filesystem.
"""

from __future__ import annotations

import functools
import random
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

DEFAULT_SIZE: Tuple[int, int] = (600, 400)

# Caps on untrusted input (CLI text, consumer-supplied size). A single test
# fixture image has no business being huge, and an unbounded instruction
# string turned into single-character line-wraps would mean thousands of
# draw calls for no benefit.
MAX_TEXT_LEN = 500
MAX_DIMENSION = 10_000

# Fixed seed for the noise backgrounds so the same fixture renders to the same
# bytes every time. Without this the noisy techniques use system randomness and
# no two renders match, which breaks golden-image tests and any detector scored
# near a threshold in CI.
DEFAULT_SEED = 1234


@functools.lru_cache(maxsize=1)
def _tofu_signature() -> Tuple[Tuple[int, int], bytes]:
    """The bundled font's .notdef bitmap. Any codepoint the font can't draw
    comes back byte-identical to this box, which is how we spot silent tofu.
    """
    mask = load_font(16).getmask("\uffff")
    return (mask.size, bytes(mask))


@functools.lru_cache(maxsize=4096)
def _font_has_glyph(ch: str) -> bool:
    """Whether the bundled font actually has a glyph for `ch` (not a tofu box)."""
    if ch.isspace():
        return True
    mask = load_font(16).getmask(ch)
    return (mask.size, bytes(mask)) != _tofu_signature()


def clip_text(text: str) -> str:
    """Cap and validate the instruction/caption text before it is rendered.

    Rejects text the bundled font can't draw: those codepoints render as
    identical .notdef boxes, so two different strings would produce the same
    image and the payload would silently encode only its character count.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")
    text = text[:MAX_TEXT_LEN]
    missing = [ch for ch in dict.fromkeys(text) if not _font_has_glyph(ch)]
    if missing:
        shown = "".join(missing[:5])
        raise ValueError(
            f"the bundled font has no glyph for {shown!r}; the injection text "
            f"would render as blank .notdef boxes. Pass text in a script the "
            f"font covers (Latin), not one it silently drops."
        )
    return text


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


def noise_background(size: Tuple[int, int], sigma: int = 40,
                     seed: int = DEFAULT_SEED) -> Image.Image:
    """A grayscale-noise 'photo-like' busy background, RGBA.

    Uses a seeded `random.Random` gaussian around mid-grey rather than
    `Image.effect_noise`, which reseeds from system randomness on every call
    and can't be pinned. Same `seed` and `sigma` give the same pixels.
    """
    rng = random.Random(seed)
    w, h = size
    data = bytes(min(255, max(0, int(rng.gauss(128, sigma)))) for _ in range(w * h))
    return Image.frombytes("L", size, data).convert("RGBA")


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
