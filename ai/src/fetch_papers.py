import arxiv

client = arxiv.Client()

def fetch_papers(query: str, max_results: int = 10, category: str | None = None):
    """
    query: phrase to search, e.g. 'graph neural networks'
    category: optional arXiv category, e.g. 'cs.LG', 'cs.CL', 'cs.AI'
    """
    full_query = f'abs:"{query}"'
    if category:
        full_query += f' AND cat:{category}'

    search = arxiv.Search(
        query=full_query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )

    results = []
    for r in client.results(search):
        results.append({
            "id": r.entry_id.split("/")[-1],
            "title": r.title,
            "abstract": r.summary,
            "authors": [a.name for a in r.authors],
            "published": r.published.isoformat(),
            "pdf_url": r.pdf_url,
            "categories": r.categories,
        })
    return results

if __name__ == "__main__":
    papers = fetch_papers("large language model,hallucination", 10, "cs.AI")
    for p in papers:
        print(p["title"], "-", p["categories"])