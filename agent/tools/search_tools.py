import os
import requests
from concurrent.futures import ThreadPoolExecutor
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

_fast_llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)

DISCLAIMER = "\n\n⚠️ This information is for educational purposes only. Always consult a licensed physician for medical advice."


def _serper_search(query: str) -> str:
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        return ""
    resp = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": 5},
        timeout=10,
    )
    if resp.status_code != 200:
        return ""
    results = resp.json().get("organic", [])
    return "\n".join(f"- {r.get('title', '')}: {r.get('snippet', '')}" for r in results)


def _nlm_search(query: str) -> str:
    resp = requests.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params={"db": "pubmed", "term": query, "retmax": 5, "retmode": "json"},
        timeout=10,
    )
    if resp.status_code != 200:
        return ""
    ids = resp.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return ""

    summary_resp = requests.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
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


@tool
def search_medical_info(query: str) -> str:
    """Search for medical information using web search and PubMed. Always appends a physician disclaimer."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        serper_future = executor.submit(_serper_search, query)
        nlm_future = executor.submit(_nlm_search, query)
        serper_results = serper_future.result()
        nlm_results = nlm_future.result()

    combined = ""
    if serper_results:
        combined += f"Web Results:\n{serper_results}\n\n"
    if nlm_results:
        combined += f"PubMed Articles:\n{nlm_results}"

    if not combined:
        return f"No results found for '{query}'." + DISCLAIMER

    prompt = f"Summarize the following medical search results about '{query}' in clear, patient-friendly language:\n\n{combined}"
    response = _fast_llm.invoke([HumanMessage(content=prompt)])
    return response.content + DISCLAIMER
