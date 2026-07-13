"""
LLM configuration for the RAG pipeline — using Groq (free tier) instead of OpenAI.

Setup steps before running anything that uses this:
1. Create a free account at https://console.groq.com
2. Generate an API key from the console (API Keys -> Create API Key)
3. Copy .env.example to a new file named .env in the same folder
4. Open .env and paste your real key in place of the placeholder:
       GROQ_API_KEY=gsk_your_actual_key_here
   .env is listed in .gitignore, so it will NEVER be committed to git --
   this keeps your API key private even if you push this project to GitHub.
5. Install the required packages:
     pip install llama-index-llms-groq llama-index-core python-dotenv
"""

import os
from dotenv import load_dotenv
from llama_index.llms.groq import Groq
from llama_index.core import Settings

# Reads the .env file in the current directory and loads its key=value pairs
# into the environment, so os.environ.get() below can find them.
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY or GROQ_API_KEY == "your-groq-api-key-here":
    raise EnvironmentError(
        "GROQ_API_KEY not found or still set to the placeholder value.\n"
        "1. Copy .env.example to .env\n"
        "2. Open .env and paste your real Groq API key\n"
        "3. Run this script again"
    )

# llama-3.3-70b-versatile is currently a strong free-tier option on Groq for RAG-style
# Q&A generation — good balance of quality and speed. Swap the model name if you want
# to try a smaller/faster one (e.g. llama-3.1-8b-instant) for quicker iteration while debugging.
llm = Groq(
    model="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY,
    temperature=0.1,  # low temperature -- we want grounded, consistent answers, not creativity
)

# Registering this as the global default LLM means every LlamaIndex component
# (query engines, response synthesizers, etc.) will use Groq automatically,
# without needing to pass llm= explicitly everywhere.
Settings.llm = llm


if __name__ == "__main__":
    # Quick sanity check -- run this file directly to confirm the API key + connection work
    response = llm.complete("In one sentence, what is a RAG pipeline?")
    print(response)