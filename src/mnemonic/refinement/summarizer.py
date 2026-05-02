import httpx
import asyncio
import json
import os
from typing import List, Optional

class LocalSummarizer:
    def __init__(self):
        from src.mnemonic.config import ensure_config_exists
        self.config_path = os.path.join(os.path.dirname(__file__), "..", "aggregator", "llm_config.json")
        ensure_config_exists(self.config_path)
        self._load_config()
        self._client: Optional[httpx.AsyncClient] = None

    def _load_config(self):
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error loading LLM config: {e}. Using defaults.")
            self.config = {
                "provider": "ollama",
                "base_url": "http://localhost:11434",
                "model": "llama3",
                "temperature": 0.7,
                "max_tokens": 1024
            }
        
        self.provider = self.config.get("provider", "ollama")
        self.base_url = self.config.get("base_url", "http://localhost:11434")
        self.model = self.config.get("model", "llama3")

    def reload_config(self):
        self._load_config()

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def summarize(self, text: str, context_items: Optional[List[dict]] = None, style: str = "concise", history: Optional[List[dict]] = None) -> str:
        if not text and not context_items:
            return ""
            
        styles = {
            "concise": "Synthesize the following search results into a concise, actionable summary (max 3-4 sentences). Use a professional tone.",
            "deep_research": "Provide a detailed a comprehensive synthesis of the following search results. Organize the information logically, highlight key contradictions or consensus, and provide a deep dive into the subject. Use a formal, academic tone.",
            "bullet_points": "Synthesize the following search results into a set of clear, high-impact bullet points. Focus on key takeaways and actionable facts.",
            "quick_summary": "Provide a very brief, 1-2 sentence 'TL;DR' summary of the following results."
        }
        
        prompt_prefix = styles.get(style, styles["concise"])
        
        if style == "deep_research" or style == "concise":
            prompt_prefix += "\n\nCRITICAL: If you find contradicting claims between the sources, explicitly highlight them (e.g., 'Source A claims X, while Source B claims Y')."

        if context_items:
            snippets = [f"Source: {item['title']}\nContent: {item['snippet']}" for item in context_items]
            prompt = f"{prompt_prefix}\n\n" + "\n---\n".join(snippets)
        else:
            prompt = f"{prompt_prefix} Summarize the following text:\n\n{text}"

        if history:
            history_text = "\n".join([f"{h['role']}: {h['content']}" for h in history[-5:]])
            prompt = f"Conversation History:\n{history_text}\n\n{prompt}"

        try:
            if self.provider == "ollama":
                return await self._call_ollama(prompt)
            elif self.provider == "llama_cpp":
                return await self._call_llama_cpp(prompt)
            else:
                return f"Unsupported LLM provider: {self.provider}"
        except Exception as e:
            return f"{self.provider.capitalize()} error: {str(e)}"

    async def _call_ollama(self, prompt: str) -> str:
        client = await self.get_client()
        response = await client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.config.get("temperature", 0.7),
                    "num_predict": self.config.get("max_tokens", 1024)
                }
            }
        )
        if response.status_code == 200:
            return response.json().get("response", "No summary generated.")
        return f"Error from Ollama: {response.status_code}"

    async def _call_llama_cpp(self, prompt: str) -> str:
        client = await self.get_client()
        # llama.cpp server uses /completion endpoint by default
        response = await client.post(
            f"{self.base_url}/completion",
            json={
                "prompt": prompt,
                "temperature": self.config.get("temperature", 0.7),
                "n_predict": self.config.get("max_tokens", 1024),
                "stream": False
            }
        )
        if response.status_code == 200:
            return response.json().get("content", "No summary generated.")
        return f"Error from llama.cpp: {response.status_code}"

    async def check_availability(self) -> bool:
        try:
            client = await self.get_client()
            if self.provider == "ollama":
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
            elif self.provider == "llama_cpp":
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
            return False
        except:
            return False
