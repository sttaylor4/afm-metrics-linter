import os
import unittest

from fontmetricslint.linter import lint_stream

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def lint_fixture(name):
    path = os.path.join(FIXTURES_DIR, name)
    with open(path, "r", encoding="latin-1") as handle:
        return list(lint_stream(handle))


def codes(findings):
    return [f.code for f in findings]


class ValidFileTests(unittest.TestCase):
    def test_no_findings(self):
        self.assertEqual(lint_fixture("valid.afm"), [])


class BrokenFileTests(unittest.TestCase):
    def setUp(self):
        self.findings = lint_fixture("broken.afm")
        self.by_code = {f.code: f for f in self.findings}

    def test_negative_width_flagged_on_its_line(self):
        finding = self.by_code["E004"]
        self.assertEqual(finding.line, 5)
        self.assertIn("-667", finding.message)

    def test_duplicate_code_flagged_on_second_occurrence(self):
        finding = self.by_code["W001"]
        self.assertEqual(finding.line, 6)
        self.assertIn("line 5", finding.message)

    def test_duplicate_name_flagged_on_second_occurrence(self):
        finding = self.by_code["W002"]
        self.assertEqual(finding.line, 6)
        self.assertIn("line 5", finding.message)

    def test_missing_end_marker_flagged_at_last_line(self):
        finding = self.by_code["E002"]
        self.assertEqual(finding.line, 7)

    def test_missing_headers_flagged(self):
        missing = [f for f in self.findings if f.code == "W003"]
        self.assertEqual(len(missing), 2)
        messages = {f.message for f in missing}
        self.assertTrue(any("FullName" in m for m in messages))
        self.assertTrue(any("FamilyName" in m for m in messages))


class KerningPairTests(unittest.TestCase):
    def setUp(self):
        self.findings = lint_fixture("kerning.afm")
        self.by_code = {f.code: f for f in self.findings}

    def test_duplicate_pair_flagged_on_second_occurrence(self):
        finding = self.by_code["W004"]
        self.assertEqual(finding.line, 13)
        self.assertIn("line 12", finding.message)

    def test_undefined_glyph_reference_flagged(self):
        finding = self.by_code["W005"]
        self.assertEqual(finding.line, 14)
        self.assertIn("'W'", finding.message)


class BoundingBoxTests(unittest.TestCase):
    def test_inverted_box_flagged(self):
        findings = lint_fixture("bad_bbox.afm")
        self.assertEqual(codes(findings), ["E006"])
        finding = findings[0]
        self.assertEqual(finding.line, 7)
        self.assertIn("40", finding.message)
        self.assertIn("10", finding.message)

    def test_valid_box_is_not_flagged(self):
        lines = [
            "StartFontMetrics 4.1\n",
            "FontName F\n",
            "FullName F\n",
            "FamilyName F\n",
            "StartCharMetrics 1\n",
            "C 32 ; WX 278 ; N space ; B 0 -10 278 700 ;\n",
            "EndCharMetrics\n",
            "EndFontMetrics\n",
        ]
        self.assertEqual(list(lint_stream(lines)), [])

    def test_unparseable_box_flagged_as_malformed(self):
        lines = [
            "StartFontMetrics 4.1\n",
            "FontName F\n",
            "FullName F\n",
            "FamilyName F\n",
            "StartCharMetrics 1\n",
            "C 32 ; WX 278 ; N space ; B 0 0 bad 700 ;\n",
            "EndCharMetrics\n",
            "EndFontMetrics\n",
        ]
        findings = list(lint_stream(lines))
        self.assertEqual(codes(findings), ["E003"])


class MalformedLineTests(unittest.TestCase):
    def test_unparseable_code_flagged(self):
        findings = lint_fixture("malformed_line.afm")
        self.assertIn("E003", codes(findings))


class MissingStartMarkerTests(unittest.TestCase):
    def test_flagged_on_first_line(self):
        findings = lint_fixture("no_start.afm")
        start_findings = [f for f in findings if f.code == "E001"]
        self.assertEqual(len(start_findings), 1)
        self.assertEqual(start_findings[0].line, 1)


class InMemoryStreamTests(unittest.TestCase):
    """Rules that are easier to exercise directly than via a fixture file."""

    def test_ch_lines_are_parsed_like_c_lines(self):
        lines = [
            "StartFontMetrics 4.1\n",
            "FontName F\n",
            "FullName F\n",
            "FamilyName F\n",
            "StartCharMetrics 1\n",
            "CH <20> ; WX -10 ; N space ;\n",
            "EndCharMetrics\n",
            "EndFontMetrics\n",
        ]
        findings = list(lint_stream(lines))
        self.assertEqual(codes(findings), ["E004"])

    def test_negative_code_is_not_treated_as_duplicate_source(self):
        # AFM uses -1 for glyphs with no standard encoding slot; several of
        # them sharing -1 is normal and should not be flagged as W001.
        lines = [
            "StartFontMetrics 4.1\n",
            "FontName F\n",
            "FullName F\n",
            "FamilyName F\n",
            "StartCharMetrics 2\n",
            "C -1 ; WX 500 ; N one ;\n",
            "C -1 ; WX 500 ; N two ;\n",
            "EndCharMetrics\n",
            "EndFontMetrics\n",
        ]
        findings = list(lint_stream(lines))
        self.assertNotIn("W001", codes(findings))

    def test_blank_lines_are_ignored(self):
        lines = [
            "StartFontMetrics 4.1\n",
            "\n",
            "FontName F\n",
            "FullName F\n",
            "FamilyName F\n",
            "   \n",
            "StartCharMetrics 1\n",
            "C 32 ; WX 278 ; N space ;\n",
            "EndCharMetrics\n",
            "EndFontMetrics\n",
        ]
        self.assertEqual(list(lint_stream(lines)), [])

    def test_empty_input_reports_missing_end_marker_at_line_one(self):
        findings = list(lint_stream([]))
        end_findings = [f for f in findings if f.code == "E002"]
        self.assertEqual(len(end_findings), 1)
        self.assertEqual(end_findings[0].line, 1)

    def test_malformed_kerning_pair_flagged(self):
        lines = [
            "StartFontMetrics 4.1\n",
            "FontName F\n",
            "FullName F\n",
            "FamilyName F\n",
            "StartCharMetrics 2\n",
            "C 65 ; WX 667 ; N A ;\n",
            "C 86 ; WX 611 ; N V ;\n",
            "EndCharMetrics\n",
            "StartKernPairs 1\n",
            "KPX A notanumber\n",
            "EndKernPairs\n",
            "EndFontMetrics\n",
        ]
        findings = list(lint_stream(lines))
        self.assertEqual(codes(findings), ["E005"])

    def test_well_formed_kerning_section_has_no_findings(self):
        lines = [
            "StartFontMetrics 4.1\n",
            "FontName F\n",
            "FullName F\n",
            "FamilyName F\n",
            "StartCharMetrics 2\n",
            "C 65 ; WX 667 ; N A ;\n",
            "C 86 ; WX 611 ; N V ;\n",
            "EndCharMetrics\n",
            "StartKernData\n",
            "StartKernPairs 1\n",
            "KPX A V -80\n",
            "EndKernPairs\n",
            "EndKernData\n",
            "EndFontMetrics\n",
        ]
        self.assertEqual(list(lint_stream(lines)), [])


if __name__ == "__main__":
    unittest.main()
