import os
from langchain_groq import ChatGroq

llm = ChatGroq(model=os.environ["LLM_MODEL"], temperature=0)
