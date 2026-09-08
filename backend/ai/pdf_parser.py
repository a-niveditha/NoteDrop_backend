import re

import pymupdf  # PyMuPDF

# Headings that signal "everything from here on is not paper content"
CUTOFF_HEADINGS = [
    r'references',
    r'bibliography',
    r'acknowledg(e)?ments?',
]

CUTOFF_PATTERN = re.compile(
    r'\n\s*(\d+\.?\s*)?(' + '|'.join(CUTOFF_HEADINGS) + r')\s*\n',
    re.IGNORECASE
)


def _extract_full_text(pdf_path: str) -> str:
    doc = pymupdf.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def _strip_trailing_sections(text: str) -> str:
    """
    Cut the text at the first occurrence of References/Bibliography/
    Acknowledgements — whichever comes FIRST, since Acknowledgements
    sometimes appears before References.
    """
    match = CUTOFF_PATTERN.search(text)
    if match:
        return text[:match.start()]
    return text


def _clean_text(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'arXiv:\d{4}\.\d{4,5}v?\d*\s*\[.*?\]\s*\d{1,2}\s\w+\s\d{4}', '', text)
    return text.strip()


def extract_text(file_path: str) -> str:
    raw = _extract_full_text(file_path)
    trimmed = _strip_trailing_sections(raw)
    return _clean_text(trimmed)
