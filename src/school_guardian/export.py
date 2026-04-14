from __future__ import annotations

import html
import io
import re
import unicodedata
from datetime import date
from pathlib import Path

from school_guardian.text_utils import normalize_for_pdf_font, normalize_math_text


def solution_to_pdf(title: str, solution_markdown: str, metadata: dict[str, str] | None = None) -> bytes:
    """Render a Markdown solution to PDF and return the raw bytes."""
    html_document = solution_to_html(title, solution_markdown, metadata=metadata)
    return html_to_pdf(html_document)


def solution_to_html(
    title: str,
    solution_markdown: str,
    metadata: dict[str, str] | None = None,
) -> str:
    """Render a Markdown solution as a styled HTML document."""
    body_html = markdown_to_html(_strip_duplicate_title(title, solution_markdown))
    safe_title = html.escape(_clean_text(title))
    meta_html = _metadata_html(metadata or {})
    return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <title>{safe_title}</title>
    <style>
      @page {{
        size: A4;
        margin: 22mm 18mm;
      }}
      body {{
        font-family: Helvetica, Arial, sans-serif;
        color: #1f2937;
        font-size: 11pt;
        line-height: 1.45;
      }}
      h1 {{
        font-size: 20pt;
        margin: 0 0 8pt 0;
        color: #111827;
      }}
      h2 {{
        font-size: 15pt;
        margin: 18pt 0 8pt 0;
        color: #111827;
      }}
      .meta {{
        margin: 0 0 14pt 0;
        color: #4b5563;
        font-size: 9.5pt;
      }}
      .meta p {{
        margin: 0 0 3pt 0;
      }}
      .meta strong {{
        color: #374151;
      }}
      h3 {{
        font-size: 12.5pt;
        margin: 14pt 0 6pt 0;
        color: #111827;
      }}
      p {{
        margin: 0 0 8pt 0;
      }}
      ul, ol {{
        margin: 0 0 10pt 18pt;
        padding: 0;
      }}
      li {{
        margin: 0 0 4pt 0;
      }}
      code {{
        font-family: Courier, monospace;
        font-size: 10pt;
        background: #f3f4f6;
        padding: 1pt 3pt;
      }}
      strong {{
        color: #111827;
      }}
      hr {{
        border: 0;
        border-top: 1px solid #d1d5db;
        margin: 12pt 0 16pt 0;
      }}
    </style>
  </head>
  <body>
    <h1>{safe_title}</h1>
    {meta_html}
    <hr />
    {body_html}
  </body>
</html>
"""


def markdown_to_html(markdown_text: str) -> str:
    """Convert Markdown to HTML, using a library when available and a simple fallback otherwise."""
    text = _normalize_markdown(normalize_math_text(markdown_text))
    try:
        import markdown as markdown_lib
    except ImportError:
        return _basic_markdown_to_html(text)

    return markdown_lib.markdown(
        text,
        extensions=["extra", "sane_lists", "nl2br"],
        output_format="html5",
    )


def html_to_pdf(html_document: str) -> bytes:
    """Render HTML to PDF bytes."""
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise RuntimeError(
            "PDF export requires the 'export' optional dependency with HTML/PDF support."
        ) from exc

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    body_html = _prepare_html_for_fpdf(_extract_body_html(html_document))
    if _configure_unicode_font(pdf):
        pdf.write_html(body_html)
    else:
        pdf.write_html(normalize_for_pdf_font(body_html))

    output = io.BytesIO()
    pdf.output(output)
    return output.getvalue()


def _basic_markdown_to_html(markdown_text: str) -> str:
    blocks: list[str] = []
    lines = markdown_text.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue

        if line == "---":
            blocks.append("<hr />")
            index += 1
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            content = _render_inline_markdown(heading_match.group(2))
            blocks.append(f"<h{level}>{content}</h{level}>")
            index += 1
            continue

        ordered_items: list[str] = []
        while index < len(lines):
            ordered_match = re.match(r"^\s*\d+\.\s+(.*)$", lines[index])
            if not ordered_match:
                break
            ordered_items.append(f"<li>{_render_inline_markdown(ordered_match.group(1))}</li>")
            index += 1
        if ordered_items:
            blocks.append("<ol>" + "".join(ordered_items) + "</ol>")
            continue

        unordered_items: list[str] = []
        while index < len(lines):
            unordered_match = re.match(r"^\s*[-*]\s+(.*)$", lines[index])
            if not unordered_match:
                break
            unordered_items.append(f"<li>{_render_inline_markdown(unordered_match.group(1))}</li>")
            index += 1
        if unordered_items:
            blocks.append("<ul>" + "".join(unordered_items) + "</ul>")
            continue

        paragraph_lines: list[str] = []
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate or candidate == "---":
                break
            if re.match(r"^(#{1,3})\s+", candidate):
                break
            if re.match(r"^\s*\d+\.\s+", lines[index]) or re.match(r"^\s*[-*]\s+", lines[index]):
                break
            paragraph_lines.append(candidate)
            index += 1
        paragraph = "<br />".join(_render_inline_markdown(part) for part in paragraph_lines)
        blocks.append(f"<p>{paragraph}</p>")

    return "\n".join(blocks)


def _render_inline_markdown(text: str) -> str:
    escaped = html.escape(_clean_text(text))
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    return escaped


def _normalize_markdown(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = (
        text.replace("\u00ad", "")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\ufeff", "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    text = "".join(ch if unicodedata.category(ch)[0] != "C" or ch in "\n\t" else " " for ch in text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def _extract_body_html(html_document: str) -> str:
    match = re.search(r"<body[^>]*>(.*)</body>", html_document, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return html_document


def _prepare_html_for_fpdf(html_document: str) -> str:
    def ordered_list_replacer(match: re.Match[str]) -> str:
        items = re.findall(r"<li>\s*(.*?)\s*</li>", match.group(1), flags=re.DOTALL)
        return "".join(f"<p>{index}. {item}</p>" for index, item in enumerate(items, start=1))

    html_document = re.sub(r"<ol>\s*(.*?)\s*</ol>", ordered_list_replacer, html_document, flags=re.DOTALL)
    html_document = re.sub(r"<ul>\s*(.*?)\s*</ul>", lambda match: re.sub(r"<li>\s*(.*?)\s*</li>", r"<p>• \1</p>", match.group(1), flags=re.DOTALL), html_document, flags=re.DOTALL)
    html_document = re.sub(r"</?(ul|ol)>", "", html_document)
    return html_document


def build_solution_metadata(
    *,
    exported_on: date | None = None,
    course_name: str | None = None,
    due_date: str | None = None,
    task_name: str | None = None,
) -> dict[str, str]:
    metadata: dict[str, str] = {}
    metadata["Exportado"] = _format_display_date(exported_on or date.today())
    if task_name:
        metadata["Tarea"] = task_name
    if course_name:
        metadata["Materia"] = course_name
    if due_date:
        metadata["Entrega"] = _format_display_date(due_date)
    return metadata


def _metadata_html(metadata: dict[str, str]) -> str:
    if not metadata:
        return ""
    lines = []
    for label, value in metadata.items():
        cleaned_value = _clean_text(value)
        if not cleaned_value:
            continue
        lines.append(f"<p><strong>{html.escape(label)}:</strong> {html.escape(cleaned_value)}</p>")
    if not lines:
        return ""
    return '<div class="meta">' + "".join(lines) + "</div>"


def _format_display_date(value: date | str) -> str:
    if isinstance(value, date):
        parsed = value
    else:
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return _clean_text(value)
    return parsed.strftime("%d/%m/%Y")


def _configure_unicode_font(pdf) -> bool:
    regular_path, bold_path = _find_pdf_font_paths()
    if regular_path is None:
        return False

    pdf.add_font("SchoolGuardianSans", "", str(regular_path))
    if bold_path is not None:
        pdf.add_font("SchoolGuardianSans", "B", str(bold_path))
    pdf.set_font("SchoolGuardianSans", size=11)
    return True


def _find_pdf_font_paths() -> tuple[Path | None, Path | None]:
    candidates = [
        (
            Path("/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf"),
        ),
        (
            Path("/usr/share/fonts/google-droid-sans-fonts/DroidSans.ttf"),
            Path("/usr/share/fonts/google-droid-sans-fonts/DroidSans-Bold.ttf"),
        ),
        (
            Path("/usr/share/fonts/google-noto-vf/NotoSans[wght].ttf"),
            None,
        ),
    ]
    for regular, bold in candidates:
        if regular.exists():
            return regular, bold if bold is not None and bold.exists() else None
    return None, None


def _strip_duplicate_title(title: str, markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    if not lines:
        return markdown_text

    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1

    if index >= len(lines):
        return markdown_text

    match = re.match(r"^#\s+(.*)$", lines[index].strip())
    if not match:
        return markdown_text

    if _clean_text(match.group(1)).casefold() != _clean_text(title).casefold():
        return markdown_text

    remaining = lines[index + 1 :]
    while remaining and not remaining[0].strip():
        remaining = remaining[1:]
    return "\n".join(remaining)
