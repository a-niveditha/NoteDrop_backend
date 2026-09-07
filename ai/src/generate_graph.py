import json
import math
import time
import os
import re
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

INPUT_FILE = Path("data/processed/kg_extractions.json")
OUTPUT_FILE = Path("data/processed/knowledge_graph.json")
CACHE_FILE = Path("data/processed/embeddings_cache.json") 

def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}

def save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))

EMBEDDING_CACHE = load_cache()

def normalize_text(text: str) -> str:
    #deduplication for casing and punctuation.
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text) # Remove punctuatio
    return text

def get_embedding(text: str) -> list[float]:
    #uses cache to avoid redundant calls to openai
    norm_text = normalize_text(text)
    
    if norm_text in EMBEDDING_CACHE:
        return EMBEDDING_CACHE[norm_text]
        
    # If not in cache, call OpenAI 
    res = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    vec = res.data[0].embedding
    EMBEDDING_CACHE[norm_text] = vec
    save_cache(EMBEDDING_CACHE)
    
    return vec

def calculate_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

#json format for 
def generate_graph():
    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found.")
        return

    raw_extractions = json.loads(INPUT_FILE.read_text())
    graph = {"nodes": [], "links": []}

    def resolve_entity(raw_name: str, entity_type: str, description: str = "") -> str:
        candidate_vec = get_embedding(raw_name)

        # 1. Check existing nodes of the SAME type
        same_type_nodes = [n for n in graph["nodes"] if n["type"] == entity_type]
        best_match = None
        best_score = -1.0

        for node in same_type_nodes:
            score = calculate_cosine_similarity(candidate_vec, node["embedding"])
            if score > best_score:
                best_score = score
                best_match = node

        # 2. Cosine Threshold >= 0.85 (Catches "CNN" vs "Convolutional Neural Network")
        if best_match and best_score >= 0.85:
            print(f"  🔗 MERGE: '{raw_name}' -> '{best_match['name']}' (Score: {best_score:.3f})")
            return best_match["id"]

        # 3. Create new node if no match
        new_id = f"{entity_type[:4].lower()}_{int(time.time() * 1000) % 100000}_{os.urandom(2).hex()}"
        print(f"  ✨ NEW NODE: '{raw_name}' ({entity_type})")
        graph["nodes"].append({
            "id": new_id,
            "name": raw_name,
            "type": entity_type,
            "description": description,
            "embedding": candidate_vec
        })
        return new_id

    for paper in raw_extractions:
        paper_id = paper.get("paper_id", f"unknown_{int(time.time())}")
        paper_title = paper_id.replace("_", " ").title()
        
        print(f"\nProcessing Paper: {paper_title}")

        # Paper Node
        paper_node_id = f"paper_{paper_id}"
        graph["nodes"].append({
            "id": paper_node_id,
            "name": paper_title,
            "type": "Paper",
            "embedding": get_embedding(paper_title)
        })

        # Process Bipartite Links
        for m in paper.get("methodologies", []):
            target_id = resolve_entity(m["name"], "Methodology", m.get("description", ""))
            graph["links"].append({"source": paper_node_id, "target": target_id, "relation": "USES_METHOD"})

        for a in paper.get("architecture", []):
            target_id = resolve_entity(a["name"], "Architecture", a.get("description", ""))
            graph["links"].append({"source": paper_node_id, "target": target_id, "relation": "USES_ARCH"})

        for p in paper.get("problem", []):
            target_id = resolve_entity(p, "Domain")
            graph["links"].append({"source": paper_node_id, "target": target_id, "relation": "APPLIED_TO"})

    # Save Output
    OUTPUT_FILE.write_text(json.dumps(graph, indent=2))
    print(f"\n✅ Saved {len(graph['nodes'])} nodes to {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_graph()