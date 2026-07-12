"""The catalog of visual prompt-injection techniques.

Every id below is stable and referenced by the README, the CLI, and the
pytest fixtures. Treat renames as breaking changes.

`ocr_expected` reflects what a default OCR pass (no contrast enhancement, no
rotation correction) is likely to recover. `fake-system-ui` and
`caption-chrome` render clean, upright, high-contrast text, which is exactly
what OCR handles well. The rest are shaped, per the published research this
package is grounded in (see README), specifically to survive being skimmed
by a human while still surviving OCR-based text filters: too low contrast,
too small, angled, embedded in noise, or blended into a busy region.
"""

from __future__ import annotations

from typing import Dict, Tuple

from . import techniques as _t
from ._util import DEFAULT_SIZE, validate_size
from .model import Technique

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
        ),
        Technique(
            id="white-on-white",
            name="White-on-white / color-matched text",
            description="Text drawn in the exact background color: zero pixel-intensity contrast against whatever base image is used.",
            ocr_expected=False,
            generate=_t.generate_white_on_white,
        ),
        Technique(
            id="tiny-corner",
            name="Tiny corner text",
            description="A short instruction in very small type tucked into a corner of the image.",
            ocr_expected=False,
            generate=_t.generate_tiny_corner,
        ),
        Technique(
            id="edge-noise",
            name="High-frequency edge region",
            description="Text embedded in a fine checkerboard, the kind of high-edge-density region that defeats naive OCR binarization.",
            ocr_expected=False,
            generate=_t.generate_edge_noise,
        ),
        Technique(
            id="fake-system-ui",
            name="Fake system-message overlay",
            description="A rounded box styled like a chat or system-message bubble, containing the instruction as if it were legitimate UI.",
            ocr_expected=True,
            generate=_t.generate_fake_system_message,
        ),
        Technique(
            id="caption-chrome",
            name="Caption / metadata chrome",
            description="A photo-credit style bar along the bottom edge, reading as image chrome rather than image content.",
            ocr_expected=True,
            generate=_t.generate_caption_chrome,
        ),
        Technique(
            id="low-opacity",
            name="Low-opacity text over a busy background",
            description="Text composited at low alpha over a noisy background.",
            ocr_expected=False,
            generate=_t.generate_low_opacity,
        ),
        Technique(
            id="rotated-skew",
            name="Rotated/skewed text",
            description="Upright text rotated to an angle, the way a watermark or an OCR-hostile payload would sit.",
            ocr_expected=False,
            generate=_t.generate_rotated,
        ),
    )
}


def list_techniques():
    """Every `Technique` in the catalog, in registration order."""
    return list(CATALOG.values())


def generate_image(technique_id: str, instruction_text: str, size: Size = DEFAULT_SIZE,
                    base_image=None):
    """Render one injection payload by technique id. Raises ValueError on an
    unknown id or an invalid size, rather than surfacing a raw KeyError.
    """
    technique = CATALOG.get(technique_id)
    if technique is None:
        known = ", ".join(sorted(CATALOG))
        raise ValueError(f"unknown technique id: {technique_id!r}. Known ids: {known}")
    size = validate_size(size)
    return technique.generate(instruction_text, size, base_image)
