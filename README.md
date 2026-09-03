# afm-metrics-linter

A linter for Adobe Font Metrics (`.afm`) files. It reads a file line by line
and reports problems -- malformed records, duplicate glyph codes, negative
advance widths, missing headers -- with the line number where each one
occurs.

## Why

AFM files are plain text, one record per line, and PDF generators, font
subsetters, and print pipelines still read them directly to figure out how
wide a glyph is before a font is fully parsed. A hand-edited or
badly-generated AFM file with a duplicate character code or a bogus width
does not usually fail loudly -- it produces text that's mispositioned or
overlapping, discovered much later in the pipeline than where it started.
This checks the file itself, before it gets to that stage.

Large CJK metrics files can have tens of thousands of `C` lines. The linter
never reads a file into memory as a whole string or list -- it walks it one
line at a time, keeping only the small amount of state each rule actually
needs (which codes and glyph names have shown up so far).

## Usage

```
afm-lint FILE [FILE ...]
```

or without installing:

```
python -m fontmetricslint.cli FILE
```

Pass `-` to read from stdin.

### Example

Given a file `broken.afm`:

```
StartFontMetrics 4.1
FontName MyFont-Regular
StartCharMetrics 3
C 32 ; WX 278 ; N space ;
C 65 ; WX -667 ; N A ;
C 65 ; WX 667 ; N A ;
EndCharMetrics
```

Running:

```
$ afm-lint broken.afm
broken.afm:5: E004 error: negative advance width (-667.0)
broken.afm:6: W001 warning: character code 65 already used on line 5
broken.afm:6: W002 warning: glyph name 'A' already used on line 5
broken.afm:7: E002 error: file does not end with EndFontMetrics
broken.afm:1: W003 warning: missing recommended header key FullName
broken.afm:1: W003 warning: missing recommended header key FamilyName
```

Exit status is `1` if any finding is an error, `0` otherwise (warnings alone
don't fail the run).

## Rules

| Code | Severity | Meaning |
| ---- | -------- | ------- |
| E001 | error    | file does not start with `StartFontMetrics` |
| E002 | error    | file does not end with `EndFontMetrics` |
| E003 | error    | a `C`/`CH` line could not be parsed |
| E004 | error    | a glyph's advance width (`WX`) is negative |
| W001 | warning  | a character code appears on more than one `C` line |
| W002 | warning  | a glyph name appears on more than one `C` line |
| W003 | warning  | a recommended header key (`FontName`, `FullName`, `FamilyName`) is missing |
| E005 | error    | a `KPX` line could not be parsed |
| W004 | warning  | a `KPX` glyph name pair appears on more than one line |
| W005 | warning  | a `KPX` line references a glyph name not defined by any `C` line |

## Installing

No third-party dependencies -- this only uses the standard library.

```
pip install -e .
```

That gives you the `afm-lint` command. Without installing, `python -m
fontmetricslint.cli` works the same way from a checkout.

## Tests

```
python -m unittest discover -s tests
```

No test runner beyond the standard library `unittest` module is required.
Fixtures live under `tests/fixtures/`.

## Status

Early. The rule set above covers the mistakes I've actually run into;
bounding box sanity and encoding-scheme checks aren't covered yet.
