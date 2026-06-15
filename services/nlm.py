import requests

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def search(query: str, max_results: int = 5) -> str:
    resp = requests.get(
        f"{BASE_URL}/esearch.fcgi",
        params={"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"},
        timeout=10,
    )
    if resp.status_code != 200:
        return ""
    ids = resp.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return ""

    summary_resp = requests.get(
        f"{BASE_URL}/esummary.fcgi",
        params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
        timeout=10,
    )
    if summary_resp.status_code != 200:
        return ""

    articles = summary_resp.json().get("result", {})
    lines = []
    for uid in ids:
        article = articles.get(uid, {})
        title = article.get("title", "")
        source = article.get("source", "")
        if title:
            lines.append(f"- {title} ({source})")
    return "\n".join(lines)
