import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from pdf_parser import parse_pdf_for_llm
from kg_extractor import extract_paper_knowledge


def process_paper(pdf_path: str, paper_id: str, output_dir: str = "data/processed") -> dict:
    text = parse_pdf_for_llm(pdf_path)
    extraction = extract_paper_knowledge(text)
    extraction["paper_id"] = paper_id

    out_path = Path(output_dir) / "kg_extractions.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if out_path.exists():
        existing = json.loads(out_path.read_text())

    # replace if this paper was already processed (idempotent reruns)
    existing = [e for e in existing if e.get("paper_id") != paper_id]
    existing.append(extraction)
    out_path.write_text(json.dumps(existing, indent=2))

    return extraction


def main():
    pdf_dir = Path("data")
    for pdf_path in pdf_dir.glob("*.pdf"):
        paper_id = pdf_path.stem
        print(f"Processing {paper_id}...")
        try:
            extraction = process_paper(str(pdf_path), paper_id)
            print(f"  ✓ {len(extraction['methodologies'])} methodologies, "
                  f"{len(extraction['architecture'])} architecture components")
        except Exception as e:
            print(f"  ✗ Failed: {e}")


if __name__ == "__main__":
    main()