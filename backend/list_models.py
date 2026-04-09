from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv

load_dotenv()

models_to_try = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash-001",
    "gemini-1.0-pro",
]

for model in models_to_try:
    try:
        llm = ChatGoogleGenerativeAI(model=model, google_api_key=os.getenv('GOOGLE_API_KEY'))
        response = llm.invoke("say hi")
        print(f"WORKS: {model}")
        break
    except Exception as e:
        print(f"FAIL: {model} — {str(e)[:80]}")

