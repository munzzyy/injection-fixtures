# Changelog

All notable changes to injection-fixtures are recorded here. Nothing has
been tagged or published yet, so everything so far sits under Unreleased.

## Unreleased

### Techniques and controls

- 14 visual prompt-injection techniques. Eight vary how visible the text
  is. Four come from Unit 42's catalog of injections seen on the live web
  and vary how it is spelled. Two stack a pair of those on one image.
  docs/techniques.md describes each one.
- 10 benign controls for measuring false positives. Most share the look of
  a technique with ordinary copy in place of the instruction.
  `BENIGN_COUNTERPART` says which control answers which technique.
- Every technique carries an `ocr_expected` label and a provenance label.
  It also declares the smallest canvas it can draw on and refuses anything
  smaller instead of handing back an image with nothing in it.
- An instruction that draws nothing is refused. That covers whitespace, a
  lone zero-width space and a bidi control the technique strips. In the
  library an empty string still renders the no-text baseline.
- Line breaks in an instruction become spaces before anything is drawn.
- A vendored subset of DejaVu Sans covers Latin, Greek and Cyrillic. It is
  renamed Injection Fixtures Sans as the Bitstream Vera terms require, and
  tools/build_font.py rebuilds it. `--font unicode` or
  `font_path=UNICODE_FONT` selects it. Text a font has no glyph for is
  refused rather than drawn as empty boxes.

### pytest plugin and library

- Installing the package registers a pytest plugin with two parametrized
  fixtures (`visual_injection_payloads` and `benign_control_images`) and
  two factories (`make_injection_image` and `make_benign_image`).
- `InjectionPayload` carries `bbox`, the pixel region the instruction landed
  in. It also carries `rendered_text` and `provenance`.
- `generate_image_with_bbox` is exported from the package.
- Every generator takes a `base_image`, a `seed` and a `font_path`.
- The package ships `py.typed`.

### CLI

- `injection-fixtures list` prints the catalog and `list --json` prints it
  as JSON.
- `injection-fixtures render` writes one technique or control. `render
  --all` writes the whole corpus with a `manifest.json` of ground truth and
  a `corpus.json` that records the package and Pillow versions.
- `render --all` moves nothing into `--out` until every image has rendered.
- `--seed` makes a run byte-reproducible with the same Pillow version.
- Bad input exits 2 with a message instead of a traceback.

### Project

- The license changed from MIT to GPL-3.0-or-later on 2026-09-25.
- A framewall catch-rate benchmark script, with a dated snapshot in
  docs/benchmarks/framewall.md.
- CI runs the tests on Linux, macOS and Windows and runs ruff on one leg.
- The release workflow builds on a v* tag and stops if the tag and the
  package version disagree. It installs the wheel once before it publishes
  to PyPI through a Trusted Publisher.
- The sdist carries everything the test suite needs, so a packager can run
  the tests from it.
- The version is set in one place, `injection_fixtures/__init__.py`.
