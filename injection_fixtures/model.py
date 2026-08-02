"""Data model for injection techniques and benign control samples."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Tuple

from PIL import Image

Size = Tuple[int, int]
InjectionGenerator = Callable[..., Image.Image]
BenignGenerator = Callable[..., Image.Image]
TextPreparer = Callable[..., str]

# Where a technique comes from. `typographic` covers the rendering categories
# described in the academic work the README cites. `in-the-wild` covers the
# ones Unit 42 catalogued from live web injections on 2026-03-03, which vary
# how the instruction is spelled rather than how visible it is.
PROVENANCE_TYPOGRAPHIC = "typographic"
PROVENANCE_IN_THE_WILD = "in-the-wild"


@dataclass(frozen=True)
class Technique:
    """One visual prompt-injection technique.

    `ocr_expected` records whether a plain OCR pass (no vision-language model,
    no contrast preprocessing) is expected to recover the injected text. It is
    a best-effort label for the consumer to filter on, not something this
    package verifies at generation time.

    `min_size` is the smallest canvas on which this technique's text still
    lands inside the image. Below it the render would come back byte-identical
    to the same render with no instruction, so `generate_image` refuses instead
    of handing back a fixture with no payload in it.

    `prepare` returns the exact string the generator draws. It is not always
    the caller's text: `homoglyph` substitutes look-alike codepoints,
    `bidi-override` reverses it, and several techniques truncate. The manifest
    written by `render --all` publishes both, so ground truth matches pixels.
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
    """A rendered injection image plus the metadata describing how it was made."""

    technique_id: str
    technique_name: str
    instruction_text: str
    ocr_expected: bool
    image: Image.Image


@dataclass(frozen=True)
class BenignPayload:
    """A rendered benign control image plus its metadata."""

    sample_id: str
    sample_name: str
    image: Image.Image
