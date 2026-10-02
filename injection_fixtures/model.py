"""Data model for injection techniques and benign control samples."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from PIL import Image

Size = Tuple[int, int]
BBox = Tuple[int, int, int, int]
InjectionGenerator = Callable[..., Image.Image]
BenignGenerator = Callable[..., Image.Image]
TextPreparer = Callable[..., str]

# Where a technique comes from. `typographic` covers the rendering categories
# described in the academic work the README cites. `in-the-wild` covers the
# ones Unit 42 catalogued from live web injections on 2026-03-03, which vary
# how the instruction is spelled rather than how visible it is. `stacked`
# covers combinations of two techniques applied to the same instruction at
# once, closer to what a live adversarial image actually does than any single
# technique applied in isolation - see PROVENANCE_IN_THE_WILD above.
PROVENANCE_TYPOGRAPHIC = "typographic"
PROVENANCE_IN_THE_WILD = "in-the-wild"
PROVENANCE_STACKED = "stacked"


@dataclass(frozen=True)
class Technique:
    """One visual prompt-injection technique.

    `ocr_expected` records whether a plain OCR pass (no vision-language model,
    no contrast preprocessing) is expected to recover the injected text. It is
    a best-effort label for the consumer to filter on, not something this
    package verifies at generation time.

    `min_size` is the smallest canvas on which this technique's text still
    lands inside the image. Below it the render would carry no payload, so
    `generate_image` refuses instead of handing back a fixture with nothing in
    it.

    `prepare(text, font_path, size=...)` returns the exact string the
    generator draws on a canvas of that size. It is not always the caller's
    text: `homoglyph` substitutes look-alike codepoints, `bidi-override`
    reverses it, and an instruction that does not fit the canvas is cut after
    the last word that does. The manifest written by `render --all` publishes
    both, so ground truth matches pixels.
    """

    id: str
    name: str
    description: str
    ocr_expected: bool
    generate: InjectionGenerator
    prepare: TextPreparer
    min_size: Size = (64, 64)
    provenance: str = PROVENANCE_TYPOGRAPHIC


@dataclass(frozen=True)
class BenignSample:
    """One benign control image generator. Carries no injected instruction."""

    id: str
    name: str
    description: str
    generate: BenignGenerator
    min_size: Size = (1, 1)


@dataclass(frozen=True)
class InjectionPayload:
    """A rendered injection image plus the metadata describing how it was made.

    `bbox` is the pixel region the instruction actually occupies, as
    `(left, top, right, bottom)`, or `None` when there is nothing to
    localize (an empty instruction, or a technique/size combination that
    ended up not drawing anything visible). It is computed the same way the
    CLI's `render --all` manifest computes `location`: by diffing the
    rendering against the same technique rendered with no instruction, so a
    consumer scoring localization gets the region that is actually different
    because of the payload, not a guess based on where the technique usually
    draws.

    `rendered_text` is the string actually in the pixels, the same value the
    manifest's `rendered_text` carries (see `rendered_instruction`).
    `provenance` is the technique's provenance label. Both default to `None`
    and come after `bbox`, so positional construction from older code keeps
    working.
    """

    technique_id: str
    technique_name: str
    instruction_text: str
    ocr_expected: bool
    image: Image.Image
    bbox: Optional[BBox] = None
    rendered_text: Optional[str] = None
    provenance: Optional[str] = None


@dataclass(frozen=True)
class BenignPayload:
    """A rendered benign control image plus its metadata."""

    sample_id: str
    sample_name: str
    image: Image.Image
