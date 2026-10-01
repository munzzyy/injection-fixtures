"""Shared rendering helpers used by both the injection techniques and the benign
control generators. Nothing here reaches the network or the filesystem.
"""

from __future__ import annotations

import functools
import os
import random
from pathlib import Path
from typing import List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

DEFAULT_SIZE: Tuple[int, int] = (600, 400)

# A font file as a str or a path object, such as UNICODE_FONT.
FontPath = Union[str, os.PathLike[str]]

# The vendored Unicode font. Pillow's bundled default font covers ASCII and
# nothing else, so an accent, a Greek letter or a Cyrillic letter has no glyph
# and gets rejected. This subset of DejaVu Sans adds Latin-1, Latin Extended-A,
# Greek and Cyrillic, which is what the `homoglyph` technique needs and what a
# non-English instruction needs. It is opt-in: pass `font_path=UNICODE_FONT` to
# a generator, or `--font` on the CLI. The default stays Pillow's bundled font
# so existing renders keep their exact pixels. See tools/build_font.py.
UNICODE_FONT: Path = Path(__file__).resolve().parent / "fonts" / "InjectionFixturesSans.ttf"

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

# Line breaks are collapsed to a single space before anything is drawn.
# Pillow's `textlength` refuses multiline input, so a newline used to reach
# `tiny-corner` and `rotated-skew` and crash them with a raw Pillow ValueError,
# while the six techniques that wrap through `wrap_text` swallowed it. One
# instruction is one run of text here, whatever whitespace the caller pasted.
LINE_BREAKS = "\r\n\v\f\u2028\u2029\u0085"


@functools.lru_cache(maxsize=8)
def _tofu_signature(font_path: Optional[FontPath]) -> Tuple[Tuple[int, int], bytes]:
    """A font's .notdef bitmap. Any codepoint the font can't draw comes back
    byte-identical to this box, which is how we spot silent tofu.
    """
    mask = load_font(16, font_path).getmask("\uffff")
    return (mask.size, bytes(mask))


@functools.lru_cache(maxsize=4096)
def _font_has_glyph(ch: str, font_path: Optional[FontPath] = None) -> bool:
    """Whether `font_path` (or the bundled font) has a real glyph for `ch`."""
    if ch.isspace():
        return True
    mask = load_font(16, font_path).getmask(ch)
    return (mask.size, bytes(mask)) != _tofu_signature(font_path)


@functools.lru_cache(maxsize=4096)
def _draws_ink(ch: str, font_path: Optional[FontPath] = None) -> bool:
    """Whether `ch` puts any pixel down. False for whitespace, and for the
    zero-width and bidi format characters a font maps to an empty glyph.
    """
    if ch.isspace():
        return False
    return any(bytes(load_font(16, font_path).getmask(ch)))


def require_visible(text: str, drawn: str, font_path: Optional[FontPath] = None) -> str:
    """Return `drawn`, or raise if a non-empty `text` came out as nothing visible.

    `drawn` is the string a technique actually puts on the canvas for `text`.
    Whitespace, a lone U+200B or a bidi control the technique strips all leave
    an image identical to the no-text render, which a detector passes for free.
    An empty `text` is the deliberate no-text baseline and is let through.
    """
    if text and not any(_draws_ink(ch, font_path) for ch in set(drawn)):
        raise ValueError(
            f"the instruction draws nothing: {text[:40]!r} is whitespace or "
            f"characters with no visible glyph, so the image would carry no payload"
        )
    return drawn


def normalize_breaks(text: str) -> str:
    """Collapse every line break in `text` to a single space."""
    # CRLF first, so a Windows line ending becomes one space and not two.
    text = text.replace("\r\n", " ")
    for ch in LINE_BREAKS:
        text = text.replace(ch, " ")
    return text


def clip_text(text: str, font_path: Optional[FontPath] = None) -> str:
    """Cap and validate the instruction/caption text before it is rendered.

    Rejects text the font can't draw: those codepoints render as identical
    .notdef boxes, so two different strings would produce the same image and
    the payload would silently encode only its character count.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")
    text = normalize_breaks(text[:MAX_TEXT_LEN])
    missing = [ch for ch in dict.fromkeys(text) if not _font_has_glyph(ch, font_path)]
    if missing:
        shown = "".join(missing[:5])
        which = "the bundled font" if font_path is None else f"the font at {font_path}"
        raise ValueError(
            f"{which} has no glyph for {shown!r}; the injection text would "
            f"render as blank .notdef boxes. The bundled font covers ASCII "
            f"only. For accents, Greek or Cyrillic pass the vendored Unicode "
            f"font: font_path=injection_fixtures.UNICODE_FONT in the library, "
            f"or --font on the CLI."
        )
    return text


def require_min_size(size: Tuple[int, int], minimum: Tuple[int, int], what: str) -> None:
    """Reject a canvas too small for `what` to actually draw its payload.

    Several techniques place their text at fixed offsets. Below a certain
    canvas the text lands off the edge and the render comes back byte-identical
    to the same render with no instruction at all: a fixture carrying no
    payload, which a detector then "passes" for free. Refusing loudly beats
    handing back a silently empty image.
    """
    if size[0] < minimum[0] or size[1] < minimum[1]:
        raise ValueError(
            f"size {size[0]}x{size[1]} is too small for {what}: it needs at "
            f"least {minimum[0]}x{minimum[1]} for the instruction to land on "
            f"the canvas. Below that the render carries no payload."
        )


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


@functools.lru_cache(maxsize=64)
def load_font(size: int, font_path: Optional[FontPath] = None) -> ImageFont.ImageFont:
    """A font at `size`: the bundled Pillow default, or the TrueType file at
    `font_path`.

    Cached because the glyph-coverage check probes one character at a time and
    reloading a TrueType file per probe is the slow part of rendering.
    """
    if font_path is not None:
        try:
            return ImageFont.truetype(os.fspath(font_path), size=size)
        except OSError as e:
            raise ValueError(f"could not load the font at {font_path}: {e}") from None
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


def canvas(size: Tuple[int, int], base_image: Optional[Image.Image],
           fill: Union[str, Tuple[int, int, int]] = "white") -> Image.Image:
    """An RGBA canvas of `size`: `base_image` resized if given, else a flat fill."""
    if base_image is not None:
        return base_image.convert("RGBA").resize(size)
    return Image.new("RGBA", size, fill)


# Each cached entry is w*h bytes, so eight entries stay under 32 MiB.
_NOISE_CACHE_MAX_PIXELS = 2048 * 2048


@functools.lru_cache(maxsize=8)
def _noise_bytes(w: int, h: int, sigma: float, seed: int) -> bytes:
    rng = random.Random(seed)
    return bytes(min(255, max(0, int(rng.gauss(128, sigma)))) for _ in range(w * h))


def noise_background(size: Tuple[int, int], sigma: int = 40,
                     seed: Optional[int] = None) -> Image.Image:
    """A grayscale-noise 'photo-like' busy background, RGBA.

    Uses a seeded `random.Random` gaussian around mid-grey rather than
    `Image.effect_noise`, which reseeds from system randomness on every call
    and can't be pinned. Same `seed` and `sigma` give the same pixels.

    The pixels are cached as immutable bytes per (size, sigma, seed), and
    every call builds a new image from them, so a caller that draws on its
    background never changes the next one.
    """
    actual_seed = seed if seed is not None else DEFAULT_SEED
    w, h = size
    make = _noise_bytes if w * h <= _NOISE_CACHE_MAX_PIXELS else _noise_bytes.__wrapped__
    return Image.frombytes("L", (w, h), make(w, h, sigma, actual_seed)).convert("RGBA")


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
