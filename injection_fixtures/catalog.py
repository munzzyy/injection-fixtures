"""The catalog of visual prompt-injection techniques.

Every id below is stable and referenced by the README, the CLI, and the
pytest fixtures. Treat renames as breaking changes.

`ocr_expected` reflects what a default OCR pass (no contrast enhancement, no
rotation correction) is likely to recover. `fake-system-ui` and
`caption-chrome` render clean, upright, high-contrast text, which is exactly
what OCR handles well. Most of the rest are shaped, per the published research
this package is grounded in (see README), specifically to survive being skimmed
by a human while still surviving OCR-based text filters: too low contrast,
too small, angled, embedded in noise, or blended into a busy region.

The four `in-the-wild` techniques work the other way round. `homoglyph` and
`split-payload` render text a plain OCR pass reads without trouble; what they
defeat is the string matching that happens after OCR. Both labels are honest
about their own layer, which is the point of the flag.
"""

from __future__ import annotations

import functools
from typing import Dict, Optional, Tuple

from PIL import ImageChops

from . import techniques as _t
from ._util import DEFAULT_SIZE, require_min_size, validate_size
from .model import PROVENANCE_IN_THE_WILD, PROVENANCE_STACKED, BBox, Technique

Size = Tuple[int, int]

CATALOG: Dict[str, Technique] = {
    t.id: t
    for t in (
        Technique(
            id="low-contrast",
            name="Low-contrast text",
            description="Text a few shades off the background color: hard for a human to notice on a skim, still a distinct pixel value.",
            ocr_expected=False,
            generate=_t.generate_low_contrast,
            prepare=_t.prepare_default,
            min_size=(32, 32),
        ),
        Technique(
            id="white-on-white",
            name="White-on-white / color-matched text",
            description="Text one shade off the background color: near-zero pixel-intensity contrast against whatever base image is used, still a real (recoverable) pixel value.",
            ocr_expected=False,
            generate=_t.generate_white_on_white,
            prepare=_t.prepare_default,
            min_size=(32, 32),
        ),
        Technique(
            id="tiny-corner",
            name="Tiny corner text",
            description="A short instruction in very small type tucked into a corner of the image.",
            ocr_expected=False,
            generate=_t.generate_tiny_corner,
            prepare=_t.prepare_tiny_corner,
            min_size=(16, 16),
        ),
        Technique(
            id="edge-noise",
            name="High-frequency edge region",
            description="Text embedded in a fine checkerboard, the kind of high-edge-density region that defeats naive OCR binarization.",
            ocr_expected=False,
            generate=_t.generate_edge_noise,
            prepare=_t.prepare_default,
            min_size=(16, 16),
        ),
        Technique(
            id="fake-system-ui",
            name="Fake system-message overlay",
            description="A rounded box styled like a chat or system-message bubble, containing the instruction as if it were legitimate UI.",
            ocr_expected=True,
            generate=_t.generate_fake_system_message,
            prepare=_t.prepare_default,
            min_size=(64, 64),
        ),
        Technique(
            id="caption-chrome",
            name="Caption / metadata chrome",
            description="A photo-credit style bar along the bottom edge, reading as image chrome rather than image content.",
            ocr_expected=True,
            generate=_t.generate_caption_chrome,
            prepare=_t.prepare_caption,
            min_size=(16, 16),
        ),
        Technique(
            id="low-opacity",
            name="Low-opacity text over a busy background",
            description="Text composited at low alpha over a noisy background.",
            ocr_expected=False,
            generate=_t.generate_low_opacity,
            prepare=_t.prepare_default,
            min_size=(32, 32),
        ),
        Technique(
            id="rotated-skew",
            name="Rotated/skewed text",
            description="Upright text rotated to an angle, the way a watermark or an OCR-hostile payload would sit.",
            ocr_expected=False,
            generate=_t.generate_rotated,
            prepare=_t.prepare_caption,
            min_size=(16, 16),
        ),
        Technique(
            id="homoglyph",
            name="Homoglyph substitution",
            description="Ordinary readable text whose Latin letters are Cyrillic look-alikes: OCR recovers it, an exact-match filter over the result does not.",
            ocr_expected=True,
            generate=_t.generate_homoglyph,
            prepare=_t.prepare_homoglyph,
            min_size=(32, 32),
            provenance=PROVENANCE_IN_THE_WILD,
        ),
        Technique(
            id="bidi-override",
            name="Right-to-left override",
            description="The instruction rendered the way a U+202E override displays it, reversed, so a literal match on the OCR output finds nothing.",
            ocr_expected=False,
            generate=_t.generate_bidi_override,
            prepare=_t.prepare_bidi,
            min_size=(32, 32),
            provenance=PROVENANCE_IN_THE_WILD,
        ),
        Technique(
            id="split-payload",
            name="Payload split across regions",
            description="One instruction cut into fragments scattered across the canvas, none of which is an instruction on its own.",
            ocr_expected=True,
            generate=_t.generate_split_payload,
            prepare=_t.prepare_split,
            min_size=(64, 64),
            provenance=PROVENANCE_IN_THE_WILD,
        ),
        Technique(
            id="color-camouflage",
            name="Color-camouflaged text in a UI panel",
            description="Text painted a few shades off the saturated colored panel it sits in, with two more panels beside it as distractors.",
            ocr_expected=False,
            generate=_t.generate_color_camouflage,
            prepare=_t.prepare_default,
            min_size=(96, 96),
            provenance=PROVENANCE_IN_THE_WILD,
        ),
        Technique(
            id="rotated-low-contrast",
            name="Rotated, low-contrast text",
            description="rotated-skew and low-contrast compounded: angled text a few shades off the background instead of full-contrast dark grey.",
            ocr_expected=False,
            generate=functools.partial(_t.generate_stacked, ["low-contrast", "rotated-skew"]),
            prepare=_t.prepare_caption,
            min_size=(32, 32),
            provenance=PROVENANCE_STACKED,
        ),
        Technique(
            id="homoglyph-tiny-corner",
            name="Homoglyph text in a tiny corner",
            description="homoglyph and tiny-corner compounded: the Cyrillic look-alike substitution, in tiny type tucked into a corner instead of a full-width paragraph.",
            ocr_expected=False,
            generate=functools.partial(_t.generate_stacked, ["homoglyph", "tiny-corner"]),
            prepare=_t.prepare_stacked_homoglyph_tiny_corner,
            min_size=(32, 32),
            provenance=PROVENANCE_STACKED,
        ),
    )
}


def list_techniques():
    """Every `Technique` in the catalog, in registration order."""
    return list(CATALOG.values())


def _technique(technique_id: str) -> Technique:
    technique = CATALOG.get(technique_id)
    if technique is None:
        known = ", ".join(sorted(CATALOG))
        raise ValueError(f"unknown technique id: {technique_id!r}. Known ids: {known}")
    return technique


def rendered_instruction(technique_id: str, instruction_text: str,
                          font_path: Optional[str] = None) -> str:
    """The exact string `generate_image` draws for this technique and text.

    Not always the text that went in: `homoglyph` swaps in look-alike
    codepoints, `bidi-override` reverses it, `tiny-corner` and `caption-chrome`
    truncate. Anything scoring a detector against this corpus needs the string
    that is actually in the pixels, not the one the caller asked for.
    """
    return _technique(technique_id).prepare(instruction_text, font_path)


def generate_image(technique_id: str, instruction_text: str, size: Size = DEFAULT_SIZE,
                    base_image=None, seed: Optional[int] = None,
                    font_path: Optional[str] = None):
    """Render one injection payload by technique id. Raises ValueError on an
    unknown id, an invalid size, or a canvas too small to carry the payload,
    rather than surfacing a raw KeyError or a silently empty image.
    """
    technique = _technique(technique_id)
    size = validate_size(size)
    require_min_size(size, technique.min_size, technique_id)
    return technique.generate(instruction_text, size, base_image, seed, font_path)


def generate_image_with_bbox(technique_id: str, instruction_text: str, size: Size = DEFAULT_SIZE,
                              base_image=None, seed: Optional[int] = None,
                              font_path: Optional[str] = None):
    """Like `generate_image`, but also returns where the instruction landed.

    Returns `(image, bbox)`. `bbox` is `(left, top, right, bottom)` in pixel
    coordinates, or `None` when there is nothing to localize (an empty
    instruction, or a technique/size combination that ended up drawing
    nothing visible). Computed by diffing the requested rendering against the
    same technique rendered with no instruction at all, rather than trusting
    any one generator to report where it drew - the same approach
    `render --all` uses for the manifest's `location` field, so `bbox` here
    always matches what that manifest would say for the same inputs.
    """
    image = generate_image(technique_id, instruction_text, size, base_image, seed, font_path)
    if not instruction_text:
        return image, None
    image_without = generate_image(technique_id, "", size, base_image, seed, font_path)
    bbox = ImageChops.difference(image, image_without).getbbox()
    return image, bbox
