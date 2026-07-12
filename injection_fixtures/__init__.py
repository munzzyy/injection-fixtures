"""injection-fixtures: visual prompt-injection test payloads as pytest fixtures.

Test infrastructure for screenshot-based and computer-use AI agents: a small
catalog of known visual prompt-injection techniques (low-contrast text, tiny
corner text, fake system-message overlays, and more), each rendered locally
with Pillow, plus a matching benign control set. Point your detector or your
agent's own defenses at this corpus in CI instead of hand-rolling one
poisoned screenshot at a time.

This is not an attack tool and not a detector. See the README for what it
is and is not.
"""

from __future__ import annotations

from .benign import BENIGN_CATALOG, generate_benign_image, list_benign_samples
from .catalog import CATALOG, generate_image, list_techniques
from .model import BenignPayload, BenignSample, InjectionPayload, Technique

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "CATALOG",
    "BENIGN_CATALOG",
    "Technique",
    "BenignSample",
    "InjectionPayload",
    "BenignPayload",
    "generate_image",
    "generate_benign_image",
    "list_techniques",
    "list_benign_samples",
]
