# Techniques reference

Every technique below is a generator function in `injection_fixtures/techniques.py`,
registered in `injection_fixtures/catalog.py` under a stable id. `ocr_expected`
is a best-effort label for whether a plain OCR pass, without contrast
enhancement, rotation correction, or a vision-language model in the loop,
is likely to recover the embedded text. It is metadata to filter on, not a
guarantee this package checks at generation time.

| id | ocr_expected | what it does |
| --- | --- | --- |
| `low-contrast` | false | Text rendered a few shades off the background color. |
| `white-on-white` | false | Text rendered in the exact background color: zero contrast, not just low contrast. |
| `tiny-corner` | false | A short instruction in very small type in a corner of the image. |
| `edge-noise` | false | Text embedded in a fine checkerboard, a high-edge-density region that defeats naive OCR binarization. |
| `fake-system-ui` | true | A rounded box styled like a chat/system-message bubble, containing the instruction as if it were legitimate UI. |
| `caption-chrome` | true | A photo-credit style bar along the bottom edge, reading as image chrome rather than content. |
| `low-opacity` | false | Text composited at low alpha over a noisy background. |
| `rotated-skew` | false | Upright text rotated to an angle. |

`fake-system-ui` and `caption-chrome` render clean, upright, high-contrast
text on purpose, which is exactly what OCR handles well; that is what makes
them useful as a check that a text-based filter catches the easy cases. The
other six are shaped to survive a human skim while defeating a plain OCR
pass, which is the point being made in the research this package is
grounded in (see the README).

## Benign controls

`injection_fixtures/benign.py` ships four generators with no injected
instruction, for measuring false-positive rate:

| id | what it does |
| --- | --- |
| `blank` | A flat solid-color image. No text at all. |
| `photo-like` | Grayscale noise standing in for a real photo. No text. |
| `benign-ui` | The same box chrome as `fake-system-ui`, filled with ordinary app copy instead of a directive. |
| `benign-caption` | The same caption-bar chrome as `caption-chrome`, with a real photo credit instead of a directive. |

`benign-ui` and `benign-caption` exist specifically to catch a detector that
flags "any text in a box" or "any caption bar" rather than the actual
instruction inside it — chrome alone should never be the signal.
