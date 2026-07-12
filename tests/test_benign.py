"""Tests for the benign control catalog: images with no injected instruction."""

from __future__ import annotations

import inspect
import io

import pytest
from PIL import Image

from injection_fixtures.benign import BENIGN_CATALOG, generate_benign_image, list_benign_samples
from injection_fixtures.catalog import CATALOG
from injection_fixtures.model import BenignSample

SAMPLE_IDS = sorted(BENIGN_CATALOG)


def test_benign_catalog_is_not_empty():
    assert len(BENIGN_CATALOG) >= 4


def test_list_benign_samples_returns_every_catalog_entry():
    assert {s.id for s in list_benign_samples()} == set(BENIGN_CATALOG)


def test_benign_catalog_ids_are_disjoint_from_technique_catalog():
    assert set(BENIGN_CATALOG).isdisjoint(set(CATALOG))


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_benign_sample_has_required_metadata(sample_id):
    sample = BENIGN_CATALOG[sample_id]
    assert isinstance(sample, BenignSample)
    assert sample.id == sample_id
    assert sample.name.strip()
    assert sample.description.strip()
    assert callable(sample.generate)


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_generate_benign_image_default_size_is_valid_png(sample_id):
    image = generate_benign_image(sample_id)
    assert image.size == (600, 400)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    assert len(buf.getvalue()) > 0
    buf.seek(0)
    reloaded = Image.open(buf)
    assert reloaded.format == "PNG"


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_generate_benign_image_custom_size(sample_id):
    image = generate_benign_image(sample_id, size=(250, 120))
    assert image.size == (250, 120)


def test_generate_benign_image_unknown_id_raises_value_error():
    with pytest.raises(ValueError, match="unknown benign sample id"):
        generate_benign_image("not-a-real-sample")


def test_generate_benign_image_rejects_invalid_size():
    with pytest.raises(ValueError):
        generate_benign_image("blank", size=(-1, 100))


def test_generate_benign_image_signature_has_no_text_parameter():
    # Benign control images have no way to carry an injected instruction: the
    # function that renders them does not even accept a text argument.
    params = inspect.signature(generate_benign_image).parameters
    assert "text" not in params
    assert "instruction_text" not in params


def test_benign_sample_dataclass_has_no_instruction_field():
    sample = BENIGN_CATALOG["blank"]
    assert not hasattr(sample, "instruction_text")
