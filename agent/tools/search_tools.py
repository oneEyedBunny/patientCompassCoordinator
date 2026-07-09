from concurrent.futures import ThreadPoolExecutor
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from agent.llm import llm
from agent.prompts import MEDICAL_SEARCH_SUMMARY_PROMPT
from services import serper, nlm

DISCLAIMER = "\n\n⚠️ This information is for educational purposes only. Always consult a licensed physician for medical advice."


@tool
def search_medical_info(query: str) -> str:
    """Search for medical information using web search and PubMed. Always appends a physician disclaimer."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        serper_future = executor.submit(serper.search, query)
        nlm_future = executor.submit(nlm.search, query)
        serper_results = serper_future.result()
        nlm_results = nlm_future.result()

    combined = ""
    if serper_results:
        combined += f"Web Results:\n{serper_results}\n\n"
    if nlm_results:
        combined += f"PubMed Articles:\n{nlm_results}"

    if not combined:
        return f"No results found for '{query}'." + DISCLAIMER

    prompt = MEDICAL_SEARCH_SUMMARY_PROMPT.format(query=query, search_results=combined)
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content + DISCLAIMER
