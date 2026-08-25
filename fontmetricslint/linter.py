"""Streaming rule checks for Adobe Font Metrics (AFM) files.

AFM is a plain-text format: one logical record per line, character metrics
one glyph per line. That structure means a linter never needs the whole
file in memory at once -- every rule here only needs the current line plus
a small amount of running state (which codes/names have been seen so far).
"""

from __future__ import annotations

from typing import Iterable, Iterator, NamedTuple, Optional


class Finding(NamedTuple):
    line: int
    code: str
    severity: str  # "error" or "warning"
    message: str


# Keys the AFM spec marks as required for a font to be usable downstream.
REQUIRED_HEADER_KEYS = ("FontName", "FullName", "FamilyName")


def _parse_char_metrics_line(line: str) -> Optional[dict]:
    """Parse a 'C ...' line into its fields, or None if it can't be parsed.

    A char metrics line packs several semicolon-separated fields onto one
    line, e.g. 'C 32 ; WX 278 ; N space ;'. Unrecognized fields are ignored
    rather than treated as errors -- the format allows vendor extensions
    (ligatures, kerning hints) we don't need to understand to check widths
    and duplicates.
    """
    fields: dict = {}
    for chunk in line.split(";"):
        parts = chunk.split()
        if not parts:
            continue
        key = parts[0]
        if key == "C" and len(parts) >= 2:
            try:
                fields["code"] = int(parts[1])
            except ValueError:
                return None
        elif key == "WX" and len(parts) >= 2:
            try:
                fields["wx"] = float(parts[1])
            except ValueError:
                return None
        elif key == "N" and len(parts) >= 2:
            fields["name"] = parts[1]
    return fields


def lint_stream(lines: Iterable[str]) -> Iterator[Finding]:
    """Lint an AFM file given as an iterable of lines.

    `lines` is consumed one line at a time and never buffered in full, so a
    file object (or stdin, or any other lazy line source) can be passed
    directly no matter how large the file is -- callers should not do
    `f.readlines()` before calling this.
    """
    seen_end = False
    first_line_seen = False
    header_keys_seen: set = set()
    codes_seen: dict = {}
    names_seen: dict = {}
    last_line_no = 0

    for line_no, raw_line in enumerate(lines, start=1):
        last_line_no = line_no
        line = raw_line.strip()
        if not line:
            continue

        if not first_line_seen:
            first_line_seen = True
            if not line.startswith("StartFontMetrics"):
                yield Finding(
                    line_no, "E001", "error",
                    "file does not start with StartFontMetrics",
                )

        if line.startswith("EndFontMetrics"):
            seen_end = True
            continue

        if line.startswith("StartCharMetrics") or line.startswith("EndCharMetrics"):
            continue

        key = line.split(None, 1)[0]
        if key in REQUIRED_HEADER_KEYS:
            header_keys_seen.add(key)

        if line.startswith("C ") or line.startswith("CH "):
            fields = _parse_char_metrics_line(line)
            if fields is None:
                yield Finding(line_no, "E003", "error", "malformed character metrics line")
                continue

            code = fields.get("code")
            wx = fields.get("wx")
            name = fields.get("name")

            if wx is not None and wx < 0:
                yield Finding(line_no, "E004", "error", f"negative advance width ({wx})")

            if code is not None and code >= 0:
                if code in codes_seen:
                    yield Finding(
                        line_no, "W001", "warning",
                        f"character code {code} already used on line {codes_seen[code]}",
                    )
                else:
                    codes_seen[code] = line_no

            if name is not None:
                if name in names_seen:
                    yield Finding(
                        line_no, "W002", "warning",
                        f"glyph name {name!r} already used on line {names_seen[name]}",
                    )
                else:
                    names_seen[name] = line_no

    if not seen_end:
        yield Finding(last_line_no or 1, "E002", "error", "file does not end with EndFontMetrics")

    for required_key in REQUIRED_HEADER_KEYS:
        if required_key not in header_keys_seen:
            yield Finding(1, "W003", "warning", f"missing recommended header key {required_key}")
