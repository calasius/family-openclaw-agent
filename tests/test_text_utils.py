from __future__ import annotations

import unittest

from school_guardian.text_utils import normalize_for_pdf_font, normalize_math_text


class NormalizeMathTextTestCase(unittest.TestCase):
    def test_normalize_common_school_latex(self) -> None:
        text = (
            "1. Primera potencia:\n"
            "( \\left(\\frac{3}{4}\\right)^1 = \\frac{3}{4} )\n"
            "2. Segunda potencia:\n"
            "( \\left(\\frac{3}{4}\\right)^2 = \\frac{3}{4} \\cdot \\frac{3}{4} = \\frac{9}{16} )"
        )

        normalized = normalize_math_text(text)

        self.assertIn("((3/4))¹ = (3/4)", normalized)
        self.assertIn("((3/4))² = (3/4) × (3/4) = (9/16)", normalized)
        self.assertNotIn("\\frac", normalized)
        self.assertNotIn("\\cdot", normalized)

    def test_normalize_square_root_and_sets(self) -> None:
        normalized = normalize_math_text(r"\sqrt{x} \in \mathbb{R}")

        self.assertEqual(normalized, "√x ∈ ℝ")

    def test_normalize_for_pdf_font_replaces_unsupported_unicode(self) -> None:
        normalized = normalize_for_pdf_font("Total pagado — vuelto y potencia x⁺²")

        self.assertEqual(normalized, "Total pagado - vuelto y potencia x^+^2")


if __name__ == "__main__":
    unittest.main()
