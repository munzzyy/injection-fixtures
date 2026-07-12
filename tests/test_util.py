"""Tests for the shared rendering helpers in `injection_fixtures._util`."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from injection_fixtures._util import (
    MAX_DIMENSION,
    MAX_TEXT_LEN,
    canvas,
    checkerboard,
    clip_text,
    line_height,
    load_font,
    near_background_color,
    noise_background,
    validate_size,
    wrap_text,
)


def test_clip_text_truncates_overlong_input():
    text = "a" * (MAX_TEXT_LEN + 200)
    clipped = clip_text(text)
    assert len(clipped) == MAX_TEXT_LEN


def test_clip_text_leaves_short_input_untouched():
    assert clip_text("hello") == "hello"


def test_clip_text_rejects_non_string():
    with pytest.raises(TypeError):
        clip_text(12345)


def test_validate_size_accepts_positive_ints():
    assert validate_size((640, 480)) == (640, 480)


def test_validate_size_coerces_numeric_strings():
    assert validate_size(("640", "480")) == (640, 480)


@pytest.mark.parametrize("bad", [(0, 10), (10, 0), (-1, 10), (10, MAX_DIMENSION + 1), "600x400"])
def test_validate_size_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        validate_size(bad)


def test_load_font_returns_usable_font():
    font = load_font(14)
    img = Image.new("RGB", (100, 40), "white")
    draw = ImageDraw.Draw(img)
    draw.text((2, 2), "hi", font=font)  # must not raise


def test_line_height_scales_with_font_size():
    small = line_height(load_font(10))
    large = line_height(load_font(30))
    assert large > small


def test_canvas_without_base_image_returns_requested_size():
    img = canvas((80, 60), None, fill="white")
    assert img.size == (80, 60)
    assert img.mode == "RGBA"


def test_canvas_with_base_image_resizes_to_requested_size():
    base = Image.new("RGB", (10, 10), (1, 2, 3))
    img = canvas((80, 60), base)
    assert img.size == (80, 60)


def test_noise_background_produces_requested_size():
    img = noise_background((40, 30))
    assert img.size == (40, 30)
    assert img.mode == "RGBA"


def test_checkerboard_produces_requested_size():
    img = checkerboard((37, 23))  # not an even multiple of the cell size
    assert img.size == (37, 23)


def test_near_background_color_zero_delta_matches_background():
    assert near_background_color((250, 250, 250), 0) == (250, 250, 250)
    assert near_background_color((5, 5, 5), 0) == (5, 5, 5)


def test_near_background_color_moves_light_background_darker():
    color = near_background_color((250, 250, 250), 6)
    assert all(c < 250 for c in color)


def test_near_background_color_moves_dark_background_lighter():
    color = near_background_color((5, 5, 5), 6)
    assert all(c > 5 for c in color)


def test_near_background_color_clamps_to_valid_range():
    assert near_background_color((2, 2, 2), 50) == (52, 52, 52)
    assert near_background_color((253, 253, 253), 50) == (203, 203, 203)


def test_wrap_text_breaks_on_word_boundaries():
    img = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(img)
    font = load_font(14)
    lines = wrap_text(draw, "one two three four five", font, max_width=60)
    assert len(lines) > 1
    assert " ".join(lines).split() == "one two three four five".split()


def test_wrap_text_splits_a_single_unbroken_word():
    img = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(img)
    font = load_font(14)
    lines = wrap_text(draw, "x" * 200, font, max_width=50)
    assert len(lines) > 1
    assert "".join(lines) == "x" * 200


def test_wrap_text_empty_string_returns_one_empty_line():
    img = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(img)
    font = load_font(14)
    assert wrap_text(draw, "", font, max_width=50) == [""]
