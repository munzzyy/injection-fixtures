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

## Adding a technique

A new technique needs three things in the same PR: a generator function in
`injection_fixtures/techniques.py` with the signature `(instruction_text,
size, base_image=None) -> Image`, an entry in `CATALOG` in
`injection_fixtures/catalog.py` with a real `ocr_expected` judgment call, and
a benign counterpart in `injection_fixtures/benign.py` if the technique adds
new visual chrome: a box, a bar, the kind of thing a naive detector flags
on sight alone instead of on the instruction inside it.

## Zero extra dependencies

Pillow is the only runtime dependency this package will ever have. If a
change needs another package, that's a reason to reconsider the change.

## License

By opening a PR you agree your contribution is offered under the project's MIT license.
