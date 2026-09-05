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
        elif key == "B" and len(parts) >= 5:
            try:
                fields["bbox"] = tuple(float(p) for p in parts[1:5])
            except ValueError:
                return None
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
    kern_pairs_seen: dict = {}
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

        if (
            line.startswith("StartKernData")
            or line.startswith("EndKernData")
            or line.startswith("StartKernPairs")
            or line.startswith("EndKernPairs")
        ):
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
            bbox = fields.get("bbox")

            if wx is not None and wx < 0:
                yield Finding(line_no, "E004", "error", f"negative advance width ({wx})")

            if bbox is not None:
                llx, lly, urx, ury = bbox
                if llx > urx or lly > ury:
                    yield Finding(
                        line_no, "E006", "error",
                        f"invalid bounding box ({llx:g} {lly:g} {urx:g} {ury:g}): "
                        "lower-left corner is past the upper-right corner",
                    )

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

        elif line.startswith("KPX "):
            # KPX first second amount -- horizontal kerning adjustment for a
            # glyph name pair. KPY (vertical) pairs aren't part of the spec
            # most tools emit, so they're left unhandled for now.
            parts = line.split()
            amount_ok = len(parts) >= 4
            if amount_ok:
                try:
                    float(parts[3])
                except ValueError:
                    amount_ok = False
            if not amount_ok:
                yield Finding(line_no, "E005", "error", "malformed kerning pair line")
                continue

            name1, name2 = parts[1], parts[2]
            pair = (name1, name2)
            if pair in kern_pairs_seen:
                yield Finding(
                    line_no, "W004", "warning",
                    f"kerning pair {name1!r}/{name2!r} already used on line {kern_pairs_seen[pair]}",
                )
            else:
                kern_pairs_seen[pair] = line_no

            # This only catches forward references reliably because KPX pairs
            # come after the char metrics section in every AFM file this
            # linter has seen; a glyph defined later would be missed.
            for glyph_name in (name1, name2):
                if glyph_name not in names_seen:
                    yield Finding(
                        line_no, "W005", "warning",
                        f"kerning pair references undefined glyph name {glyph_name!r}",
                    )

    if not seen_end:
        yield Finding(last_line_no or 1, "E002", "error", "file does not end with EndFontMetrics")

    for required_key in REQUIRED_HEADER_KEYS:
        if required_key not in header_keys_seen:
            yield Finding(1, "W003", "warning", f"missing recommended header key {required_key}")
