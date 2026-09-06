import json
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()

client = OpenAI()  # reads OPENAI_API_KEY from env

KG_EXTRACTION_SCHEMA = {
    "name": "extract_paper_knowledge",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "problem": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The core problem(s) or task(s) the paper addresses, e.g. 'Traffic prediction'."
            },
            "methodologies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Short canonical name, e.g. 'Graph Attention Network'"},
                        "description": {"type": "string", "description": "1-2 sentence description of how it's used in this paper"}
                    },
                    "required": ["name", "description"],
                    "additionalProperties": False
                },
                "description": "Core methods/techniques the paper proposes or applies."
            },
            "architecture": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Component name, e.g. 'LSTM'"},
                        "description": {"type": "string", "description": "Its role in the system, e.g. 'Used as decoder for temporal prediction.'"}
                    },
                    "required": ["name", "description"],
                    "additionalProperties": False
                },
                "description": "Concrete architectural components/models used to implement the methodology."
            },
            "limitations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Limitations of the approach, stated or reasonably inferred."
            }
        },
        "required": ["problem", "methodologies", "architecture", "limitations"],
        "additionalProperties": False
    }
}


def extract_paper_knowledge(paper_text: str, max_chars: int = 60000) -> dict:
    if len(paper_text) > max_chars:
        paper_text = paper_text[:max_chars]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=2000,
        response_format={
            "type": "json_schema",
            "json_schema": KG_EXTRACTION_SCHEMA
        },
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a research paper analysis assistant. Extract structured "
                    "knowledge graph data from academic papers. For methodologies and "
                    "architecture components, give each a short canonical name (as commonly "
                    "known in the field) and a description of how it's specifically used in "
                    "this paper. For limitations, include what the paper explicitly states, "
                    "and if it doesn't state any, infer reasonable limitations from the "
                    "methodology and experimental setup."
                )
            },
            {
                "role": "user",
                "content": f"PAPER TEXT:\n{paper_text}"
            }
        ]
    )

    return json.loads(response.choices[0].message.content)


if __name__ == "__main__":
    from pdf_parser import parse_pdf_for_llm

    text = parse_pdf_for_llm("data/example.pdf")
    result = extract_paper_knowledge(text)
    print(json.dumps(result, indent=2))