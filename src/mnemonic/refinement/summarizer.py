import httpx
import asyncio
import json
from typing import List, Optional

from src.mnemonic.config import config

class LocalSummarizer:
    def __init__(self, base_url: str = config.OLLAMA_BASE_URL, model: str = config.OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model

    async def summarize(self, text: str, context_items: Optional[List[dict]] = None) -> str:
        if not text and not context_items:
            return ""
            
        # If context_items are provided, we are synthesizing a group of results
        if context_items:
            snippets = [f"Source: {item['title']}\nContent: {item['snippet']}" for item in context_items]
            prompt = "Synthesize the following search results into a concise, actionable summary (max 3-4 sentences). Use a professional tone.\n\n" + "\n---\n".join(snippets)
        else:
            prompt = f"Summarize the following text in 2-3 concise sentences:\n\n{text}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                if response.status_code == 200:
                    return response.json().get("response", "No summary generated.")
                else:
                    return f"Error from Ollama: {response.status_code}"
        except Exception as e:
            return f"Ollama not available: {str(e)}"

    async def check_availability(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False
