"""Integration tests for the pytest plugin surface.

These use pytest's own `pytester` fixture to run a throwaway test file in a
fresh pytest session and check what actually got collected and run, the same
way a consumer's `pip install injection-fixtures` would pick the fixtures up
through the `pytest11` entry point (see pyproject.toml). No mocking of the
plugin machinery: this is the real registration path.
"""

from __future__ import annotations

from injection_fixtures.benign import BENIGN_CATALOG
from injection_fixtures.catalog import CATALOG


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
