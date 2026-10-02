"""Integration tests for the pytest plugin surface.

These use pytest's own `pytester` fixture to run a throwaway test file in a
fresh pytest session and check what actually got collected and run, the same
way a consumer's `pip install injection-fixtures` would pick the fixtures up
through the `pytest11` entry point (see pyproject.toml). No mocking of the
plugin machinery: this is the real registration path.
"""

from __future__ import annotations

from PIL import Image

import injection_fixtures
from injection_fixtures.benign import BENIGN_CATALOG
from injection_fixtures.catalog import CATALOG
from injection_fixtures.model import InjectionPayload


def test_visual_injection_payloads_fixture_covers_the_whole_catalog(pytester):
    pytester.makepyfile(
        test_consumer="""
        def test_payload_is_a_valid_image(visual_injection_payloads):
            payload = visual_injection_payloads
            assert payload.image.size == (600, 400)
            assert payload.technique_id
            assert payload.instruction_text
            assert isinstance(payload.ocr_expected, bool)
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=len(CATALOG))


def test_visual_injection_payloads_fixture_carries_a_bbox(pytester):
    # bbox has to be usable straight off the fixture, no CLI manifest and no
    # second render, since that is the whole point of adding it here.
    pytester.makepyfile(
        test_consumer="""
        def test_payload_bbox_is_inside_the_image(visual_injection_payloads):
            payload = visual_injection_payloads
            assert payload.bbox is not None
            left, top, right, bottom = payload.bbox
            w, h = payload.image.size
            assert 0 <= left < right <= w
            assert 0 <= top < bottom <= h
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=len(CATALOG))


def test_benign_control_images_fixture_covers_the_whole_catalog(pytester):
    pytester.makepyfile(
        test_consumer="""
        def test_control_is_a_valid_image(benign_control_images):
            payload = benign_control_images
            assert payload.image.size == (600, 400)
            assert payload.sample_id
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=len(BENIGN_CATALOG))


def test_make_injection_image_factory_is_usable_directly(pytester):
    pytester.makepyfile(
        test_consumer="""
        def test_it(make_injection_image):
            payload = make_injection_image("tiny-corner", "do the thing now")
            assert payload.technique_id == "tiny-corner"
            assert payload.instruction_text == "do the thing now"
            assert payload.image.size[0] > 0
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_make_injection_image_factory_bbox_is_none_only_for_empty_text(pytester):
    pytester.makepyfile(
        test_consumer="""
        def test_it(make_injection_image):
            with_text = make_injection_image("tiny-corner", "do the thing now")
            assert with_text.bbox is not None

            without_text = make_injection_image("tiny-corner", "")
            assert without_text.bbox is None
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_make_injection_image_factory_rejects_unknown_id(pytester):
    pytester.makepyfile(
        test_consumer="""
        import pytest

        def test_it(make_injection_image):
            with pytest.raises(ValueError):
                make_injection_image("not-a-real-technique", "x")
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_make_injection_image_factory_enforces_size_caps(pytester):
    # The factory used to call the generator directly, skipping validate_size,
    # so a test author could render a 10001px fixture the CLI would reject. It
    # must now enforce the same caps as the library entry point.
    pytester.makepyfile(
        test_consumer="""
        import pytest

        def test_it(make_injection_image):
            with pytest.raises(ValueError):
                make_injection_image("low-contrast", "hi", size=(0, 0))
            with pytest.raises(ValueError):
                make_injection_image("low-contrast", "hi", size=(10001, 10))
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_make_benign_image_factory_is_usable_directly(pytester):
    pytester.makepyfile(
        test_consumer="""
        def test_it(make_benign_image):
            payload = make_benign_image("photo-like")
            assert payload.sample_id == "photo-like"
            assert payload.image.size[0] > 0
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_plugin_registers_without_an_explicit_pytest_plugins_line(pytester):
    # No `pytest_plugins = [...]` anywhere in this temp project: the fixture
    # must still be found purely through the installed package's entry point.
    pytester.makepyfile(
        test_consumer="""
        def test_it(visual_injection_payloads):
            assert visual_injection_payloads.technique_id
        """
    )
    result = pytester.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(passed=len(CATALOG))


def test_injection_payload_still_takes_its_original_six_fields_positionally():
    image = Image.new("RGB", (4, 4))
    payload = InjectionPayload("low-contrast", "Low-contrast text", "hi", False, image, (0, 0, 1, 1))
    assert payload.bbox == (0, 0, 1, 1)
    assert payload.rendered_text is None
    assert payload.provenance is None


def test_visual_injection_payloads_carry_rendered_text_and_provenance(pytester):
    pytester.makepyfile(
        test_consumer="""
        from injection_fixtures import CATALOG, rendered_instruction

        def test_it(visual_injection_payloads):
            payload = visual_injection_payloads
            assert payload.rendered_text
            assert payload.rendered_text == rendered_instruction(payload.technique_id, payload.instruction_text)
            assert payload.provenance == CATALOG[payload.technique_id].provenance
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=len(CATALOG))


def test_make_injection_image_carries_rendered_text_and_provenance(pytester):
    pytester.makepyfile(
        test_consumer="""
        from injection_fixtures import CATALOG, UNICODE_FONT, rendered_instruction

        def test_it(make_injection_image):
            payload = make_injection_image("homoglyph", "ignore this")
            assert payload.rendered_text == rendered_instruction("homoglyph", "ignore this")
            assert payload.rendered_text != "ignore this"
            assert payload.provenance == CATALOG["homoglyph"].provenance

            accented = make_injection_image("bidi-override", "café", font_path=UNICODE_FONT)
            assert accented.rendered_text == "éfac"
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_make_injection_image_reports_the_text_drawn_at_its_size(pytester):
    pytester.makepyfile(
        test_consumer="""
        from injection_fixtures import rendered_instruction

        def test_it(make_injection_image):
            payload = make_injection_image("color-camouflage", size=(300, 150))
            assert payload.rendered_text == rendered_instruction(
                "color-camouflage", payload.instruction_text, size=(300, 150))
            assert payload.rendered_text != payload.instruction_text
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_generate_image_with_bbox_is_exported_from_the_package():
    from injection_fixtures import generate_image_with_bbox

    assert "generate_image_with_bbox" in injection_fixtures.__all__
    image, bbox = generate_image_with_bbox("low-contrast", "Ignore this")
    assert image.size == (600, 400)
    assert bbox is not None
