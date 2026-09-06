import pymupdf  # PyMuPDF
import re

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


def extract_full_text(pdf_path: str) -> str:
    doc = pymupdf.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def strip_trailing_sections(text: str) -> str:
    """
    Cut the text at the first occurrence of References/Bibliography/
    Acknowledgements — whichever comes FIRST, since Acknowledgements
    sometimes appears before References.
    """
    match = CUTOFF_PATTERN.search(text)
    if match:
        return text[:match.start()]
    return text


def clean_text(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'arXiv:\d{4}\.\d{4,5}v?\d*\s*\[.*?\]\s*\d{1,2}\s\w+\s\d{4}', '', text)
    return text.strip()


def parse_pdf_for_llm(pdf_path: str) -> str:
    raw = extract_full_text(pdf_path)
    trimmed = strip_trailing_sections(raw)
    return clean_text(trimmed)


if __name__ == "__main__":
    text = parse_pdf_for_llm("data/example.pdf")
    print(f"Extracted {len(text)} chars")
    print(text[:500])