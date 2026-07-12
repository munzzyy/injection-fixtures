"""Data model for injection techniques and benign control samples."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from PIL import Image

Size = Tuple[int, int]
InjectionGenerator = Callable[[str, Size, Optional[Image.Image]], Image.Image]
BenignGenerator = Callable[[Size, Optional[Image.Image]], Image.Image]


@dataclass(frozen=True)
class Technique:
    """One visual prompt-injection technique.

    `ocr_expected` records whether a plain OCR pass (no vision-language model,
    no contrast preprocessing) is expected to recover the injected text. It is
    a best-effort label for the consumer to filter on, not something this
    package verifies at generation time.
    """

    id: str
    name: str
    description: str
    ocr_expected: bool
    generate: InjectionGenerator


@dataclass(frozen=True)
class BenignSample:
    """One benign control image generator. Carries no injected instruction."""

    id: str
    name: str
    description: str
    generate: BenignGenerator


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
