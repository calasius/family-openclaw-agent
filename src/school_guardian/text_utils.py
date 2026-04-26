from __future__ import annotations

import re
import unicodedata


_SUPERSCRIPT_MAP = str.maketrans({
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "+": "⁺",
    "-": "⁻",
    "=": "⁼",
    "(": "⁽",
    ")": "⁾",
    "n": "ⁿ",
    "i": "ⁱ",
})
_SUPERSCRIPT_CHARS = set("0123456789+-=()ni")

_LATEX_REPLACEMENTS = [
    (r"\left(", "("),
    (r"\right)", ")"),
    (r"\left[", "["),
    (r"\right]", "]"),
    (r"\left\{", "{"),
    (r"\right\}", "}"),
    (r"\cdot", "×"),
    (r"\times", "×"),
    (r"\div", "÷"),
    (r"\pm", "±"),
    (r"\geq", "≥"),
    (r"\ge", "≥"),
    (r"\leq", "≤"),
    (r"\le", "≤"),
    (r"\neq", "≠"),
    (r"\ne", "≠"),
    (r"\notin", "∉"),
    (r"\infty", "∞"),
    (r"\in", "∈"),
    (r"\mathbb{R}", "ℝ"),
    (r"\mathbb{Q}", "ℚ"),
    (r"\mathbb{Z}", "ℤ"),
    (r"\mathbb{N}", "ℕ"),
]


def normalize_math_text(text: str) -> str:
    normalized = text

    for latex, replacement in _LATEX_REPLACEMENTS:
        normalized = normalized.replace(latex, replacement)

    normalized = _replace_frac(normalized)
    normalized = _replace_sqrt(normalized)
    normalized = _replace_powers(normalized)
    normalized = normalized.replace("\\", "")
    normalized = re.sub(r"\(\s+", "(", normalized)
    normalized = re.sub(r"\s+\)", ")", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized.strip()


def normalize_for_pdf_font(text: str) -> str:
    replacements = {
        "—": "-",
        "–": "-",
        "−": "-",
        "•": "-",
        "…": "...",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "×": "x",
        "÷": "/",
        "±": "+/-",
        "≥": ">=",
        "≤": "<=",
        "≠": "!=",
        "∉": "not in",
        "∞": "infinity",
        "∈": "in",
        "ℝ": "R",
        "ℚ": "Q",
        "ℤ": "Z",
        "ℕ": "N",
        "√": "sqrt",
        "⁰": "^0",
        "¹": "^1",
        "²": "^2",
        "³": "^3",
        "⁴": "^4",
        "⁵": "^5",
        "⁶": "^6",
        "⁷": "^7",
        "⁸": "^8",
        "⁹": "^9",
        "⁺": "^+",
        "⁻": "^-",
        "⁼": "^=",
        "⁽": "^(",
        "⁾": "^)",
        "ⁿ": "^n",
        "ⁱ": "^i",
        "ᵃ": "^a",
        "ᵇ": "^b",
        "ᶜ": "^c",
        "ᵈ": "^d",
        "ᵉ": "^e",
        "ᶠ": "^f",
        "ᵍ": "^g",
        "ʰ": "^h",
        "ᶦ": "^i",
        "ʲ": "^j",
        "ᵏ": "^k",
        "ˡ": "^l",
        "ᵐ": "^m",
        "ᵒ": "^o",
        "ᵖ": "^p",
        "ʳ": "^r",
        "ˢ": "^s",
        "ᵗ": "^t",
        "ᵘ": "^u",
        "ᵛ": "^v",
        "ʷ": "^w",
        "ˣ": "^x",
        "ʸ": "^y",
        "ᶻ": "^z",
        "ᴬ": "^A",
        "ᴮ": "^B",
        "ᴰ": "^D",
        "ᴱ": "^E",
        "ᴳ": "^G",
        "ᴴ": "^H",
        "ᴵ": "^I",
        "ᴶ": "^J",
        "ᴷ": "^K",
        "ᴸ": "^L",
        "ᴹ": "^M",
        "ᴺ": "^N",
        "ᴼ": "^O",
        "ᴾ": "^P",
        "ᴿ": "^R",
        "ᵀ": "^T",
        "ᵁ": "^U",
        "ⱽ": "^V",
        "ᵂ": "^W",
    }
    normalized = text
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = normalized.encode("latin-1", "ignore").decode("latin-1")
    return normalized


def _replace_frac(text: str) -> str:
    pattern = re.compile(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
    while True:
        updated = pattern.sub(lambda match: f"({match.group(1)}/{match.group(2)})", text)
        if updated == text:
            return text
        text = updated


def _replace_sqrt(text: str) -> str:
    pattern = re.compile(r"\\sqrt\s*\{([^{}]+)\}")
    while True:
        updated = pattern.sub(lambda match: f"√{match.group(1)}", text)
        if updated == text:
            return text
        text = updated


def _replace_powers(text: str) -> str:
    text = re.sub(r"\^\{([^{}]+)\}", lambda match: _to_superscript(match.group(1)), text)
    text = re.sub(r"\^([0-9ni+\-=()]+)", lambda match: _to_superscript(match.group(1)), text)
    return text


def _to_superscript(value: str) -> str:
    if all(char in _SUPERSCRIPT_CHARS for char in value):
        return value.translate(_SUPERSCRIPT_MAP)
    return f"^({value})"
