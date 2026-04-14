from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from school_guardian.export import (
    build_solution_metadata,
    markdown_to_html,
    solution_to_html,
    solution_to_pdf,
)


class ExportPdfTestCase(unittest.TestCase):
    def test_markdown_to_html_supports_headings_and_lists(self) -> None:
        html = markdown_to_html(
            "# Titulo\n\n## Respuestas\n\n1. Primera respuesta\n2. Segunda **respuesta**\n\n- Punto A\n- Punto B"
        )

        self.assertIn("<h1>Titulo</h1>", html)
        self.assertIn("<h2>Respuestas</h2>", html)
        self.assertIn("<ol>", html)
        self.assertIn("<li>Primera respuesta</li>", html)
        self.assertIn("<strong>respuesta</strong>", html)
        self.assertIn("<ul>", html)

    def test_solution_to_html_wraps_markdown_in_document(self) -> None:
        html = solution_to_html(
            "Past Simple vs Past Continuous",
            "## Solucion\n\n1. I was making breakfast when my mom woke up.",
        )

        self.assertIn("<title>Past Simple vs Past Continuous</title>", html)
        self.assertIn("<h1>Past Simple vs Past Continuous</h1>", html)
        self.assertIn("<h2>Solucion</h2>", html)
        self.assertIn("<ol>", html)

    def test_solution_to_html_omits_duplicate_markdown_title(self) -> None:
        html = solution_to_html(
            "Past Simple vs Past Continuous",
            "# Past Simple vs Past Continuous\n\n## Respuestas\n\n1. Example",
        )

        self.assertEqual(html.count("<h1>Past Simple vs Past Continuous</h1>"), 1)

    def test_solution_to_html_renders_metadata_block(self) -> None:
        html = solution_to_html(
            "Checklist",
            "- Item",
            metadata=build_solution_metadata(
                exported_on=date(2026, 4, 11),
                task_name="Past Simple vs Past Continuous",
                course_name="Ingles",
                due_date="2026-04-12",
            ),
        )

        self.assertIn('<div class="meta">', html)
        self.assertIn("<strong>Exportado:</strong> 11/04/2026", html)
        self.assertIn("<strong>Tarea:</strong> Past Simple vs Past Continuous", html)
        self.assertIn("<strong>Materia:</strong> Ingles", html)
        self.assertIn("<strong>Entrega:</strong> 12/04/2026", html)

    def test_build_solution_metadata_formats_dates_for_people(self) -> None:
        metadata = build_solution_metadata(
            exported_on=date(2026, 4, 11),
            task_name="Trabajo practico",
            course_name="Historia",
            due_date="2026-04-15",
        )

        self.assertEqual(metadata["Exportado"], "11/04/2026")
        self.assertEqual(metadata["Tarea"], "Trabajo practico")
        self.assertEqual(metadata["Entrega"], "15/04/2026")

    def test_solution_to_pdf_uses_html_rendering(self) -> None:
        with patch("school_guardian.export.html_to_pdf", return_value=b"%PDF-fake") as html_to_pdf:
            pdf_bytes = solution_to_pdf(
                "Checklist",
                "- First bullet item\n- Second bullet item with more text",
            )

        self.assertEqual(pdf_bytes, b"%PDF-fake")
        html_to_pdf.assert_called_once()
        rendered_html = html_to_pdf.call_args.args[0]
        self.assertIn("<ul>", rendered_html)
        self.assertIn("<h1>Checklist</h1>", rendered_html)

    def test_solution_to_pdf_strips_duplicate_title_before_rendering(self) -> None:
        with patch("school_guardian.export.html_to_pdf", return_value=b"%PDF-fake") as html_to_pdf:
            solution_to_pdf(
                "Checklist",
                "# Checklist\n\n1. First item",
            )

        rendered_html = html_to_pdf.call_args.args[0]
        self.assertEqual(rendered_html.count("<h1>Checklist</h1>"), 1)

    def test_solution_to_html_normalizes_school_math_latex(self) -> None:
        html = solution_to_html(
            "Potencias",
            r"## Paso a paso" "\n\n" r"1. \left(\frac{3}{4}\right)^2 = \frac{3}{4} \cdot \frac{3}{4} = \frac{9}{16}",
        )

        self.assertIn("(3/4)", html)
        self.assertIn("×", html)
        self.assertIn("²", html)
        self.assertNotIn(r"\frac", html)

    def test_solution_to_html_makes_text_safe_for_pdf_fonts(self) -> None:
        html = solution_to_html(
            "Reporte — Matemática",
            "Potencia x⁺² y una lista:\n- valor…",
        )

        self.assertIn("Reporte — Matemática", html)
        self.assertIn("x⁺²", html)
        self.assertIn("valor…", html)


if __name__ == "__main__":
    unittest.main()
