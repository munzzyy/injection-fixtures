#!/usr/bin/env python3
"""Rebuild the vendored Unicode font from a system copy of DejaVu Sans.

The package ships one font file, `injection_fixtures/fonts/InjectionFixturesSans.ttf`.
It exists because Pillow's bundled default font covers ASCII and nothing else,
so an instruction containing an accent, a Greek letter or a Cyrillic letter has
no glyph to draw and gets rejected. The `homoglyph` technique needs Cyrillic and
Greek look-alikes by definition, and a consumer testing a multilingual payload
needs the rest.

The vendored file is a subset of DejaVu Sans 2.37: Basic Latin, Latin-1
Supplement, Latin Extended-A, Greek, Cyrillic, the punctuation and bidi format
block, and currency symbols. That covers the scripts this corpus can express
and keeps the file under 70KB instead of the 750KB full face. No CJK: adding it
would multiply the package size and none of the shipped techniques need it.

The DejaVu license permits modification only if the result is renamed away from
the Bitstream and Vera names, so the subset is renamed to "Injection Fixtures
Sans". The full license text ships next to the font in
`injection_fixtures/fonts/LICENSE-DejaVu.txt`.

Run it when the subset needs new codepoints:

    python tools/build_font.py --source /usr/share/fonts/TTF/DejaVuSans.ttf

Needs fonttools, which is not a dependency of this package. Install it just for
the rebuild: `pip install fonttools`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Basic Latin, Latin-1 Supplement, Latin Extended-A, Greek, Cyrillic,
# General Punctuation (dashes, quotes, the bidi format controls, zero-width
# space) and currency symbols.
UNICODE_RANGES = ",".join([
    "U+0020-007E",
    "U+00A0-00FF",
    "U+0100-017F",
    "U+0370-03FF",
    "U+0400-04FF",
    "U+2010-2027",
    "U+202A-202E",
    "U+2030-205E",
    "U+20A0-20BF",
])

FAMILY = "Injection Fixtures Sans"
POSTSCRIPT = "InjectionFixturesSans"
DEFAULT_SOURCE = Path("/usr/share/fonts/TTF/DejaVuSans.ttf")
OUTPUT = Path(__file__).resolve().parent.parent / "injection_fixtures" / "fonts" / "InjectionFixturesSans.ttf"


def rename(path: Path) -> None:
    """Point every name-table record at the new family name.

    DejaVu inherits the Bitstream Vera license, which allows modified copies
    only under a name containing neither "Bitstream" nor "Vera". A subset is a
    modification, so the name table has to change with it.
    """
    from fontTools.ttLib import TTFont

    font = TTFont(str(path))
    name_table = font["name"]
    replacements = {
        1: FAMILY,
        3: f"{FAMILY}; subset of DejaVu Sans 2.37",
        4: FAMILY,
        6: POSTSCRIPT,
        16: FAMILY,
    }
    for record in list(name_table.names):
        if record.nameID in replacements:
            name_table.setName(replacements[record.nameID], record.nameID,
                               record.platformID, record.platEncID, record.langID)
    font.save(str(path))
    font.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                        help=f"DejaVuSans.ttf to subset (default: {DEFAULT_SOURCE})")
    parser.add_argument("--out", type=Path, default=OUTPUT,
                        help=f"where to write the subset (default: {OUTPUT})")
    args = parser.parse_args(argv)

    if not args.source.is_file():
        print(f"build_font: no such font: {args.source}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", "fontTools.subset", str(args.source),
         f"--unicodes={UNICODE_RANGES}",
         "--layout-features=",
         "--no-hinting",
         "--desubroutinize",
         "--name-IDs=*",
         "--drop-tables+=DSIG",
         f"--output-file={args.out}"],
        check=False,
    )
    if proc.returncode != 0:
        print("build_font: fontTools.subset failed", file=sys.stderr)
        return proc.returncode

    rename(args.out)
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
