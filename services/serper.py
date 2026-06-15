import os
import requests


def search(query: str, num_results: int = 5) -> str:
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        return ""
    resp = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": num_results},
        timeout=10,
    )
    if resp.status_code != 200:
        return ""
    results = resp.json().get("organic", [])
    return "\n".join(f"- {r.get('title', '')}: {r.get('snippet', '')}" for r in results)
