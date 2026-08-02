# Contributing

Small, single-purpose tool. Contributions welcome.

## Setup

```
git clone https://github.com/munzzyy/injection-fixtures
cd injection-fixtures
pip install -e ".[dev]"
```

## Running the tests

```
pytest
```

CI runs the same command across Linux, macOS, and Windows on Python 3.9 through 3.13.

## Lint

```
pip install -e ".[lint]"
ruff check .
```

CI runs the same check on one Linux leg. The ruff version is pinned in
`pyproject.toml` so a new release can't turn CI red on its own. Bump it
deliberately.

## Adding a technique

A new technique needs four things in the same PR:

- a generator function in `injection_fixtures/techniques.py` with the
  signature `(instruction_text, size, base_image=None, seed=None,
  font_path=None) -> Image`
- a `prepare` function returning the exact string the generator draws, so the
  ground-truth manifest records what is in the pixels rather than what the
  caller passed in
- an entry in `CATALOG` in `injection_fixtures/catalog.py` with a real
  `ocr_expected` judgment call and a `min_size` the technique actually needs
- a benign counterpart in `injection_fixtures/benign.py` if the technique adds
  new visual chrome: a box, a bar, a panel, the kind of thing a naive detector
  flags on sight alone instead of on the instruction inside it

Two rules the test suite enforces, so it's cheaper to know them up front.
Renders are byte-reproducible: same input, same bytes, on every machine, which
rules out unseeded randomness. And a technique either carries its instruction
or raises. Returning an image that looks fine but has no payload in it is the
one failure mode this package exists to prevent, because a detector scored
against it passes for free.

## Zero extra dependencies

Pillow is the only runtime dependency this package will ever have. If a
change needs another package, that's a reason to reconsider the change.

The vendored font in `injection_fixtures/fonts/` is package data, not a
dependency, and does not count against this rule. Rebuild it with
`tools/build_font.py`, which needs fonttools installed just for the rebuild.
Anything else that would ship as a data file should be small, licensed for
redistribution, and shipped with its license text next to it.

## License

By opening a PR you agree your contribution is offered under the project's MIT license.
</content>
