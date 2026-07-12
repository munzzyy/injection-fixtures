"""Generator functions for each visual prompt-injection technique.

Every function has the signature `(instruction_text, size=DEFAULT_SIZE,
base_image=None) -> Image.Image`. `base_image`, when given, is resized to
`size` and used as the canvas instead of the technique's default background,
so a consumer can test against their own screenshots.

These generators render text locally with Pillow. Nothing here reads the
network or writes to disk; the caller decides what to do with the returned
image.
"""

from __future__ import annotations

from typing import Optional, Tuple

from PIL import Image, ImageDraw

from ._util import (
    DEFAULT_SIZE,
    canvas,
    checkerboard,
    clip_text,
    line_height,
    load_font,
    near_background_color,
    noise_background,
    wrap_text,
)

Size = Tuple[int, int]


def _color_matched_paragraph(
    instruction_text: str,
    size: Size,
    base_image: Optional[Image.Image],
    fill,
    font_size: int,
    delta: int,
) -> Image.Image:
    """Shared body for `low-contrast` and `white-on-white`: draw text whose
    color is sampled `delta` shades away from the background pixel under it.
    """
    text = clip_text(instruction_text)
    img = canvas(size, base_image, fill=fill).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font(font_size)
    margin = 14
    lines = wrap_text(draw, text, font, size[0] - 2 * margin)
    y = margin
    lh = line_height(font)
    for line in lines:
        sample_x = min(margin, size[0] - 1)
        sample_y = min(y, size[1] - 1)
        bg = img.getpixel((sample_x, sample_y))
        color = near_background_color(bg, delta)
        draw.text((margin, y), line, font=font, fill=color)
        y += lh
    return img


def generate_low_contrast(instruction_text: str, size: Size = DEFAULT_SIZE,
                           base_image: Optional[Image.Image] = None) -> Image.Image:
    """Text a few shades off the background color: easy to miss on a skim,
    still a distinct pixel value.
    """
    return _color_matched_paragraph(instruction_text, size, base_image,
                                     fill=(246, 246, 244), font_size=16, delta=6)


def generate_white_on_white(instruction_text: str, size: Size = DEFAULT_SIZE,
                             base_image: Optional[Image.Image] = None) -> Image.Image:
    """Text drawn in the exact background color: zero pixel-intensity contrast,
    invisible in principle, not just in practice.
    """
    return _color_matched_paragraph(instruction_text, size, base_image,
                                     fill=(255, 255, 255), font_size=16, delta=0)


def generate_tiny_corner(instruction_text: str, size: Size = DEFAULT_SIZE,
                          base_image: Optional[Image.Image] = None) -> Image.Image:
    """A short line of very small text tucked into a corner."""
    text = clip_text(instruction_text)[:80]
    img = canvas(size, base_image, fill="white").convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font(7)
    w, h = size
    tw = draw.textlength(text, font=font)
    x = max(1, w - int(tw) - 3)
    y = max(1, h - 12)
    draw.text((x, y), text, font=font, fill=(90, 90, 90))
    return img


def generate_edge_noise(instruction_text: str, size: Size = DEFAULT_SIZE,
                         base_image: Optional[Image.Image] = None) -> Image.Image:
    """Text embedded in a high-frequency checkerboard region, alternating
    colors line to line so it keeps blending into the pattern's edges.
    """
    text = clip_text(instruction_text)
    if base_image is not None:
        img = base_image.convert("RGB").resize(size)
    else:
        img = checkerboard(size).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font(14)
    w, h = size
    box_w = int(w * 0.7)
    x0 = (w - box_w) // 2
    y0 = int(h * 0.35)
    lines = wrap_text(draw, text, font, box_w - 10)
    lh = line_height(font)
    for i, line in enumerate(lines):
        color = (235, 235, 235) if i % 2 == 0 else (20, 20, 20)
        draw.text((x0 + 5, y0 + i * lh), line, font=font, fill=color)
    return img


def generate_fake_system_message(instruction_text: str, size: Size = DEFAULT_SIZE,
                                  base_image: Optional[Image.Image] = None) -> Image.Image:
    """A rounded box styled like a chat/system-message bubble, containing the
    instruction as if it were a legitimate UI element.
    """
    text = clip_text(instruction_text)
    img = canvas(size, base_image, fill=(235, 238, 242)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = size
    margin = int(w * 0.08)
    box = (margin, int(h * 0.3), w - margin, int(h * 0.7))
    draw.rounded_rectangle(box, radius=10, fill=(255, 255, 255), outline=(120, 120, 130), width=2)
    label_font = load_font(11)
    body_font = load_font(14)
    draw.text((box[0] + 14, box[1] + 10), "SYSTEM", font=label_font, fill=(150, 30, 30))
    lines = wrap_text(draw, text, body_font, (box[2] - box[0]) - 28)
    y = box[1] + 30
    lh = line_height(body_font)
    for line in lines:
        draw.text((box[0] + 14, y), line, font=body_font, fill=(20, 20, 20))
        y += lh
    return img


def generate_caption_chrome(instruction_text: str, size: Size = DEFAULT_SIZE,
                             base_image: Optional[Image.Image] = None) -> Image.Image:
    """A photo-credit style bar along the bottom edge, reading as image chrome
    rather than content.
    """
    text = clip_text(instruction_text)[:120]
    img = noise_background(size, sigma=18) if base_image is None else canvas(size, base_image)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = size
    font = load_font(10)
    bar_h = 22
    draw.rectangle((0, h - bar_h, w, h), fill=(0, 0, 0))
    draw.text((6, h - bar_h + 5), text, font=font, fill=(210, 210, 210))
    return img


def generate_low_opacity(instruction_text: str, size: Size = DEFAULT_SIZE,
                          base_image: Optional[Image.Image] = None) -> Image.Image:
    """Text at low alpha composited over a busy background."""
    text = clip_text(instruction_text)
    base = noise_background(size, sigma=45) if base_image is None else canvas(size, base_image)
    base = base.convert("RGBA")
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = load_font(20)
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
                      base_image: Optional[Image.Image] = None) -> Image.Image:
    """Text rendered upright then rotated, the way a watermark or a
    deliberately OCR-hostile payload would sit at an angle.
    """
    text = clip_text(instruction_text)[:120]
    img = canvas(size, base_image, fill="white").convert("RGBA")
    font = load_font(18)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    tw = int(probe.textlength(text, font=font)) + 8
    th = line_height(font, default=24) + 12
    tmp = Image.new("RGBA", (max(tw, 1), th), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((2, 2), text, font=font, fill=(40, 40, 40, 255))
    rotated = tmp.rotate(22, expand=True, resample=Image.BICUBIC)
    x = max(0, (size[0] - rotated.width) // 2)
    y = max(0, (size[1] - rotated.height) // 2)
    img.paste(rotated, (x, y), rotated)
    return img.convert("RGB")
