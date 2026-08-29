"""Generator functions for each visual prompt-injection technique.

Every function has the signature `(instruction_text, size=DEFAULT_SIZE,
base_image=None, seed=None, font_path=None) -> Image.Image`. `base_image`, when
given, is resized to `size` and used as the canvas instead of the technique's
default background, so a consumer can test against their own screenshots.
`font_path` swaps in a TrueType file for the ASCII-only bundled font.

Each technique also exposes how it prepares the instruction before drawing it
(the `prepare_*` functions below). Two of them rewrite the text: `homoglyph`
substitutes Cyrillic look-alikes, `bidi-override` reverses it. The catalog
publishes those prepared strings so the ground-truth manifest records what is
actually in the pixels, not just what the caller passed in.

These generators render text locally with Pillow. Nothing here reads the
network or writes to disk; the caller decides what to do with the returned
image.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from ._util import (
    DEFAULT_SIZE,
    UNICODE_FONT,
    canvas,
    checkerboard,
    clip_text,
    line_height,
    load_font,
    near_background_color,
    noise_background,
    normalize_breaks,
    wrap_text,
)

Size = Tuple[int, int]

# Latin characters and the Cyrillic codepoints that look identical in almost
# every typeface. Substituting them leaves the rendering visually unchanged but
# makes an exact-match filter over the OCR output miss: "Ignore" and the same
# word with a Cyrillic o and e are different strings that draw the same shapes.
# Taken from the confusable set Unit 42 observed in live web injections.
HOMOGLYPHS = {
    "a": "\u0430", "c": "\u0441", "e": "\u0435", "i": "\u0456", "j": "\u0458",
    "o": "\u043e", "p": "\u0440", "s": "\u0455", "x": "\u0445", "y": "\u0443",
    "A": "\u0410", "B": "\u0412", "C": "\u0421", "E": "\u0415", "H": "\u041d",
    "I": "\u0406", "K": "\u041a", "M": "\u041c", "O": "\u041e", "P": "\u0420",
    "S": "\u0405", "T": "\u0422", "X": "\u0425", "Y": "\u0423",
}

# The Unicode bidi format controls. `bidi-override` strips them out of the
# caller's text and renders their effect instead, so the fixture does not
# depend on whether the local Pillow was built with a bidi-capable layout
# engine. Same input, same pixels, on every machine.
BIDI_CONTROLS = "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"

# Filler copy interleaved with the fragments of `split-payload`, so the image
# reads as an ordinary page with unrelated lines rather than one instruction
# that happens to be spaced out.
SPLIT_FILLER = ("Quarterly summary", "Attachments (3)", "Last edited Tuesday")

# Panel colors for `color-camouflage`: a saturated UI surface, plus two
# distractor panels so a detector cannot just look for "the one colored box".
PANEL_COLORS = ((36, 84, 148), (30, 110, 78), (150, 96, 20))


def prepare_default(text: str, font_path: Optional[str] = None) -> str:
    """The instruction as drawn by most techniques: capped and glyph-checked."""
    return clip_text(text, font_path)


def prepare_tiny_corner(text: str, font_path: Optional[str] = None) -> str:
    """`tiny-corner` draws one short line, so it takes the first 80 characters."""
    return clip_text(text, font_path)[:80]


def prepare_caption(text: str, font_path: Optional[str] = None) -> str:
    """`caption-chrome` and `rotated-skew` draw one line, capped at 120."""
    return clip_text(text, font_path)[:120]


def prepare_homoglyph(text: str, font_path: Optional[str] = None) -> str:
    """Swap every Latin character that has a Cyrillic look-alike.

    The glyph check runs after the substitution, against the Unicode font,
    because the substituted string is the one that has to draw.
    """
    swapped = "".join(HOMOGLYPHS.get(ch, ch) for ch in normalize_breaks(text))
    return clip_text(swapped, font_path or UNICODE_FONT)


def prepare_bidi(text: str, font_path: Optional[str] = None) -> str:
    """Drop any bidi control the caller passed, then reverse the text.

    A U+202E right-to-left override makes a viewer see the characters in
    reverse while the underlying string stays readable to anything reading
    codepoints. There is no text layer in a PNG, so the fixture renders what
    the override would put on screen: the instruction, backwards.
    """
    stripped = "".join(ch for ch in text if ch not in BIDI_CONTROLS)
    return clip_text(stripped, font_path)[::-1]


def split_fragments(text: str, font_path: Optional[str] = None, parts: int = 3) -> List[str]:
    """Break the instruction into `parts` word-aligned fragments.

    Each fragment is meaningless on its own; only the concatenation is the
    instruction. This is the shape Unit 42 catalogued as payload splitting.
    """
    words = clip_text(text, font_path).split()
    if not words:
        return [""] * parts
    per = max(1, -(-len(words) // parts))
    chunks = [" ".join(words[i:i + per]) for i in range(0, len(words), per)]
    while len(chunks) < parts:
        chunks.append("")
    return chunks[:parts]


def prepare_split(text: str, font_path: Optional[str] = None) -> str:
    """The reassembled instruction, which is what a detector has to recover."""
    return " ".join(part for part in split_fragments(text, font_path) if part)


def _color_matched_paragraph(
    instruction_text: str,
    size: Size,
    base_image: Optional[Image.Image],
    fill,
    font_size: int,
    delta: int,
    font_path: Optional[str] = None,
) -> Image.Image:
    """Shared body for `low-contrast` and `white-on-white`: draw text `delta`
    shades away from whatever sits under each glyph.

    The shift is computed per pixel, not once per line, so the contrast stays
    exactly `delta` even where the text crosses a busy base image. Sampling a
    single background pixel per line painted the whole line in that one color,
    which destroyed the underlying content and blew the contrast wide open on
    any non-flat base.
    """
    text = prepare_default(instruction_text, font_path)
    img = canvas(size, base_image, fill=fill).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font(font_size, font_path)
    margin = 14
    lines = wrap_text(draw, text, font, size[0] - 2 * margin)

    mask = Image.new("L", size, 0)
    mask_draw = ImageDraw.Draw(mask)
    y = margin
    lh = line_height(font)
    for line in lines:
        mask_draw.text((margin, y), line, font=font, fill=255)
        y += lh

    # `near_background_color` as a per-channel lookup: light pixels move down by
    # `delta`, dark pixels move up, so covered pixels sit exactly `delta` off the
    # background under them. Pasting through the text mask leaves everything else
    # untouched.
    shifted = img.point(lambda c: max(0, c - delta) if c >= 128 else min(255, c + delta))
    img.paste(shifted, (0, 0), mask)
    return img


def generate_low_contrast(instruction_text: str, size: Size = DEFAULT_SIZE,
                           base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                           font_path: Optional[str] = None) -> Image.Image:
    """Text a few shades off the background color: easy to miss on a skim,
    still a distinct pixel value.
    """
    return _color_matched_paragraph(instruction_text, size, base_image,
                                     fill=(246, 246, 244), font_size=16, delta=6,
                                     font_path=font_path)


def generate_white_on_white(instruction_text: str, size: Size = DEFAULT_SIZE,
                             base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                             font_path: Optional[str] = None) -> Image.Image:
    """Text one shade off the background color: imperceptible to a human, still
    a real pixel value carrying the payload.

    Uses `delta=1` rather than `0` on purpose. Truly zero contrast produces a
    blank image with no recoverable text at all, which is a broken fixture, not
    a hard one: the injected string has to actually exist in the pixels.
    """
    return _color_matched_paragraph(instruction_text, size, base_image,
                                     fill=(255, 255, 255), font_size=16, delta=1,
                                     font_path=font_path)


def generate_tiny_corner(instruction_text: str, size: Size = DEFAULT_SIZE,
                          base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                          font_path: Optional[str] = None) -> Image.Image:
    """A short line of very small text tucked into a corner."""
    text = prepare_tiny_corner(instruction_text, font_path)
    img = canvas(size, base_image, fill="white").convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font(7, font_path)
    w, h = size
    tw = draw.textlength(text, font=font)
    x = max(1, w - int(tw) - 3)
    y = max(1, h - 12)
    draw.text((x, y), text, font=font, fill=(90, 90, 90))
    return img


def generate_edge_noise(instruction_text: str, size: Size = DEFAULT_SIZE,
                         base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                         font_path: Optional[str] = None) -> Image.Image:
    """Text embedded in a high-frequency checkerboard region, alternating
    colors line to line so it keeps blending into the pattern's edges.
    """
    text = prepare_default(instruction_text, font_path)
    if base_image is not None:
        img = base_image.convert("RGB").resize(size)
    else:
        img = checkerboard(size).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font(14, font_path)
    w, h = size
    box_w = int(w * 0.7)
    x0 = (w - box_w) // 2
    y0 = int(h * 0.35)
    lines = wrap_text(draw, text, font, box_w - 10)
    lh = line_height(font)
    if base_image is not None:
        # Stamp the checkerboard only under the text so the technique keeps its
        # defining high-frequency region on a caller's base image. Without this
        # the alternating fills land on plain background: the light line goes
        # invisible and the dark line reads as ordinary black text.
        patch_h = lh * max(1, len(lines)) + 10
        patch = checkerboard((box_w, patch_h)).convert("RGB")
        img.paste(patch, (x0, y0))
    for i, line in enumerate(lines):
        color = (235, 235, 235) if i % 2 == 0 else (20, 20, 20)
        draw.text((x0 + 5, y0 + i * lh), line, font=font, fill=color)
    return img


def generate_fake_system_message(instruction_text: str, size: Size = DEFAULT_SIZE,
                                  base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                                  font_path: Optional[str] = None) -> Image.Image:
    """A rounded box styled like a chat/system-message bubble, containing the
    instruction as if it were a legitimate UI element.
    """
    text = prepare_default(instruction_text, font_path)
    img = canvas(size, base_image, fill=(235, 238, 242)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = size
    margin = int(w * 0.08)
    box = (margin, int(h * 0.3), w - margin, int(h * 0.7))
    draw.rounded_rectangle(box, radius=10, fill=(255, 255, 255), outline=(120, 120, 130), width=2)
    label_font = load_font(11, font_path)
    body_font = load_font(14, font_path)
    draw.text((box[0] + 14, box[1] + 10), "SYSTEM", font=label_font, fill=(150, 30, 30))
    lines = wrap_text(draw, text, body_font, (box[2] - box[0]) - 28)
    y = box[1] + 30
    lh = line_height(body_font)
    for line in lines:
        draw.text((box[0] + 14, y), line, font=body_font, fill=(20, 20, 20))
        y += lh
    return img


def generate_caption_chrome(instruction_text: str, size: Size = DEFAULT_SIZE,
                             base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                             font_path: Optional[str] = None) -> Image.Image:
    """A photo-credit style bar along the bottom edge, reading as image chrome
    rather than content.
    """
    text = prepare_caption(instruction_text, font_path)
    img = noise_background(size, sigma=18, seed=seed) if base_image is None else canvas(size, base_image)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = size
    font = load_font(10, font_path)
    bar_h = 22
    draw.rectangle((0, h - bar_h, w, h), fill=(0, 0, 0))
    draw.text((6, h - bar_h + 5), text, font=font, fill=(210, 210, 210))
    return img


def generate_low_opacity(instruction_text: str, size: Size = DEFAULT_SIZE,
                          base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                          font_path: Optional[str] = None) -> Image.Image:
    """Text at low alpha composited over a busy background."""
    text = prepare_default(instruction_text, font_path)
    base = noise_background(size, sigma=45, seed=seed) if base_image is None else canvas(size, base_image)
    base = base.convert("RGBA")
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = load_font(20, font_path)
    margin = 16
    lines = wrap_text(draw, text, font, size[0] - 2 * margin)
    y = margin
    lh = line_height(font, default=24)
    for line in lines:
        draw.text((margin, y), line, font=font, fill=(255, 255, 255, 28))
        y += lh
    composed = Image.alpha_composite(base, overlay)
    return composed.convert("RGB")


def generate_rotated(instruction_text: str, size: Size = DEFAULT_SIZE,
                      base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                      font_path: Optional[str] = None) -> Image.Image:
    """Text rendered upright then rotated, the way a watermark or a
    deliberately OCR-hostile payload would sit at an angle.
    """
    text = prepare_caption(instruction_text, font_path)
    img = canvas(size, base_image, fill="white").convert("RGBA")
    font = load_font(18, font_path)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    tw = int(probe.textlength(text, font=font)) + 8
    th = line_height(font, default=24) + 12
    tmp = Image.new("RGBA", (max(tw, 1), th), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((2, 2), text, font=font, fill=(40, 40, 40, 255))
    rotated = tmp.rotate(22, expand=True, resample=Image.BICUBIC)
    # Center the rotated layer on the canvas. When it is wider or taller than
    # the canvas (small sizes), the offset goes negative and crops it, instead
    # of clamping to (0, 0) which pushed every glyph off-canvas and rendered a
    # blank image below roughly 180px wide.
    x = (size[0] - rotated.width) // 2
    y = (size[1] - rotated.height) // 2
    img.paste(rotated, (x, y), rotated)
    return img.convert("RGB")


def generate_homoglyph(instruction_text: str, size: Size = DEFAULT_SIZE,
                        base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                        font_path: Optional[str] = None) -> Image.Image:
    """Plain, readable text whose letters are Cyrillic look-alikes.

    Nothing here hides the instruction from a human or from OCR: the pixels are
    ordinary dark-on-light type. The evasion is one layer down, in whatever
    matches the recovered string against a blocklist. It needs a font with
    Cyrillic in it, so it defaults to the vendored Unicode font.
    """
    text = prepare_homoglyph(instruction_text, font_path)
    font_file = font_path or UNICODE_FONT
    img = canvas(size, base_image, fill=(250, 250, 248)).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font(16, font_file)
    margin = 14
    lines = wrap_text(draw, text, font, size[0] - 2 * margin)
    y = margin
    lh = line_height(font)
    for line in lines:
        draw.text((margin, y), line, font=font, fill=(35, 35, 40))
        y += lh
    return img


def generate_bidi_override(instruction_text: str, size: Size = DEFAULT_SIZE,
                            base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                            font_path: Optional[str] = None) -> Image.Image:
    """The instruction under a right-to-left override: drawn in reverse.

    On a page, U+202E flips the display order of everything after it, so a
    reader sees one thing and a parser reading codepoints sees another. A PNG
    has no codepoints, so this renders the display side: the reversed text a
    viewer would actually see. A detector that OCRs the image and matches the
    result literally comes up empty; one that also tries the reversal does not.
    """
    text = prepare_bidi(instruction_text, font_path)
    img = canvas(size, base_image, fill=(252, 250, 245)).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font(16, font_path)
    margin = 16
    lines = wrap_text(draw, text, font, size[0] - 2 * margin)
    y = margin
    lh = line_height(font)
    for line in lines:
        draw.text((margin, y), line, font=font, fill=(30, 30, 35))
        y += lh
    return img


def generate_split_payload(instruction_text: str, size: Size = DEFAULT_SIZE,
                            base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                            font_path: Optional[str] = None) -> Image.Image:
    """One instruction cut into fragments and scattered across the canvas.

    Every fragment is high-contrast and trivially readable, and no fragment is
    an instruction by itself. It only becomes one after a detector stitches the
    regions back together in reading order, which region-at-a-time scanning
    never does.
    """
    fragments = split_fragments(instruction_text, font_path)
    img = canvas(size, base_image, fill=(255, 255, 255)).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font(15, font_path)
    filler_font = load_font(11, font_path)
    w, h = size
    margin = max(4, w // 40)
    lh = line_height(font)
    band = max(lh + 6, h // 4)
    for i, fragment in enumerate(fragments):
        y = margin + i * band
        # Alternate sides so the fragments never form one readable column.
        x = margin if i % 2 == 0 else max(margin, w // 2)
        for line in wrap_text(draw, fragment, font, w - x - margin):
            draw.text((x, y), line, font=font, fill=(25, 25, 30))
            y += lh
        filler = SPLIT_FILLER[i % len(SPLIT_FILLER)]
        draw.text((margin, min(h - 12, y + 4)), filler, font=filler_font, fill=(150, 150, 155))
    return img


def panels(draw: ImageDraw.ImageDraw, size: Size, font_path: Optional[str]):
    """Draw the three colored panels shared by `color-camouflage` and its
    benign control `benign-panel`.

    Returns the panel boxes and the y offset where body text starts inside
    one, both scaled from the canvas. A short canvas gets a smaller heading
    rather than a body line pushed off the bottom of its panel.
    """
    w, h = size
    pad = max(3, min(w, h) // 40)
    panel_h = max(12, (h - pad * 4) // 3)
    heading_size = max(6, min(11, panel_h // 3))
    heading_font = load_font(heading_size, font_path)
    body_top = max(4, pad) + line_height(heading_font, default=14)
    boxes = []
    for i, color in enumerate(PANEL_COLORS):
        top = pad + i * (panel_h + pad)
        box = (pad, top, w - pad, top + panel_h)
        draw.rectangle(box, fill=color)
        draw.text((box[0] + 8, box[1] + 4), f"Panel {i + 1}", font=heading_font,
                  fill=(255, 255, 255))
        boxes.append(box)
    return boxes, body_top


def generate_color_camouflage(instruction_text: str, size: Size = DEFAULT_SIZE,
                               base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                               font_path: Optional[str] = None) -> Image.Image:
    """Text painted a few shades off the colored panel it sits in.

    `low-contrast` hides text on a near-white page. This hides it inside a
    saturated UI surface, with two more panels beside it as distractors, which
    is the shape Unit 42 catalogued as color camouflage. A detector tuned to
    grayscale contrast against a light background has nothing to fire on.
    """
    text = prepare_default(instruction_text, font_path)
    img = canvas(size, base_image, fill=(244, 244, 246)).convert("RGB")
    draw = ImageDraw.Draw(img)
    boxes, body_top = panels(draw, size, font_path)
    box = boxes[0]
    panel_h = box[3] - box[1]
    font = load_font(max(6, min(13, int((panel_h - body_top) / 1.35))), font_path)
    fill = near_background_color(PANEL_COLORS[0], 10)
    y = box[1] + body_top
    lh = line_height(font)
    drawn = 0
    for line in wrap_text(draw, text, font, (box[2] - box[0]) - 16):
        if y + lh > box[3]:
            break
        draw.text((box[0] + 8, y), line, font=font, fill=fill)
        y += lh
        drawn += 1
    if text and not drawn:
        # Refuse rather than hand back a panel row with the instruction
        # silently missing from it. `min_size` is meant to catch this before
        # we get here; if it did not, say so instead of returning a fixture
        # that carries no payload.
        raise ValueError(
            f"size {size[0]}x{size[1]} leaves no room for color-camouflage text "
            f"inside its panel; render it at {size[0]}x{size[1] * 2} or larger"
        )
    return img


def prepare_stacked_homoglyph_tiny_corner(text: str, font_path: Optional[str] = None) -> str:
    """`homoglyph-tiny-corner` draws one short line, so it takes homoglyph's
    substitution then tiny-corner's 80-character cap, in that order: the
    substitution has to run on the full instruction, the same as it would for
    `homoglyph` alone, not on an already-truncated fragment of it.
    """
    return prepare_homoglyph(text, font_path)[:80]


def generate_stacked_rotated_low_contrast(instruction_text: str, size: Size = DEFAULT_SIZE,
                                           base_image: Optional[Image.Image] = None,
                                           seed: Optional[int] = None,
                                           font_path: Optional[str] = None) -> Image.Image:
    """`rotated-skew` and `low-contrast` compounded: the same text rotated to
    an angle, in a color a few shades off the background instead of
    `rotated-skew`'s own full-contrast dark grey.

    A defense tuned to catch either trick alone - grayscale contrast against a
    light background, or an angled text region - has less to fire on here
    than it would against either technique by itself.
    """
    text = prepare_caption(instruction_text, font_path)
    fill = (255, 255, 255)
    img = canvas(size, base_image, fill=fill).convert("RGBA")
    font = load_font(18, font_path)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    tw = int(probe.textlength(text, font=font)) + 8
    th = line_height(font, default=24) + 12
    tmp = Image.new("RGBA", (max(tw, 1), th), (0, 0, 0, 0))
    text_color = near_background_color(fill, 6)
    ImageDraw.Draw(tmp).text((2, 2), text, font=font, fill=(*text_color, 255))
    rotated = tmp.rotate(22, expand=True, resample=Image.BICUBIC)
    # Same off-canvas clamp as generate_rotated: center, then let a negative
    # offset crop instead of pushing the layer past the edge.
    x = (size[0] - rotated.width) // 2
    y = (size[1] - rotated.height) // 2
    img.paste(rotated, (x, y), rotated)
    return img.convert("RGB")


def generate_stacked_homoglyph_tiny_corner(instruction_text: str, size: Size = DEFAULT_SIZE,
                                            base_image: Optional[Image.Image] = None,
                                            seed: Optional[int] = None,
                                            font_path: Optional[str] = None) -> Image.Image:
    """`homoglyph` and `tiny-corner` compounded: the Cyrillic-substituted
    instruction, in tiny type tucked into a corner instead of a full-width
    paragraph.

    Either trick alone leaves an opening: homoglyph's paragraph is easy for a
    human to spot even if a filter misses it, tiny-corner's plain ASCII text
    is exact-matchable if a filter does OCR it. Stacked, a defense has to both
    notice the corner and try the reversal-and-lookalike normalization on
    whatever it finds there.
    """
    text = prepare_stacked_homoglyph_tiny_corner(instruction_text, font_path)
    font_file = font_path or UNICODE_FONT
    img = canvas(size, base_image, fill="white").convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font(7, font_file)
    w, h = size
    tw = draw.textlength(text, font=font)
    x = max(1, w - int(tw) - 3)
    y = max(1, h - 12)
    draw.text((x, y), text, font=font, fill=(90, 90, 90))
    return img


# Registered stacked combinations, keyed by the sorted pair of component
# technique ids. Not every pair of techniques composes into something
# meaningful - two background-replacement techniques would just have one
# overwrite the other's canvas - so this is a short, deliberately curated
# list rather than every combination the catalog could produce.
STACKED_GENERATORS: Dict[Tuple[str, str], Callable[..., Image.Image]] = {
    tuple(sorted(("low-contrast", "rotated-skew"))): generate_stacked_rotated_low_contrast,
    tuple(sorted(("homoglyph", "tiny-corner"))): generate_stacked_homoglyph_tiny_corner,
}


def generate_stacked(technique_ids: List[str], instruction_text: str, size: Size = DEFAULT_SIZE,
                      base_image: Optional[Image.Image] = None, seed: Optional[int] = None,
                      font_path: Optional[str] = None) -> Image.Image:
    """Render `instruction_text` with two techniques' transforms compounded
    rather than either one applied alone.

    `technique_ids` must be exactly one of the pairs in `STACKED_GENERATORS`,
    in any order. This does not generically compose any two generators - most
    pairs would just have one overwrite the other's canvas - it dispatches to
    a hand-built combination that actually stacks the two mechanisms on the
    same rendering.
    """
    key = tuple(sorted(technique_ids))
    generator = STACKED_GENERATORS.get(key)
    if generator is None:
        known = ", ".join(" + ".join(pair) for pair in sorted(STACKED_GENERATORS))
        raise ValueError(
            f"no stacked combination registered for {list(technique_ids)!r}. "
            f"Known combinations: {known}"
        )
    return generator(instruction_text, size, base_image, seed, font_path)
