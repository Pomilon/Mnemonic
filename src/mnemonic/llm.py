import httpx
import json
import os
from typing import Optional

class LocalLLM:
    def __init__(self):
        from src.mnemonic.config import ensure_config_exists
        self.config_path = os.path.join(os.path.dirname(__file__), "aggregator", "llm_config.json")
        ensure_config_exists(self.config_path)
        self.config = self._load_config()


    def _load_config(self):
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except Exception as e:
            self.config = {
                "provider": "ollama",
                "base_url": "http://localhost:11434",
                "model": "llama3",
                "temperature": 0.7
            }
        
        self.provider = self.config.get("provider", "ollama")
        self.base_url = self.config.get("base_url", "http://localhost:11434")
        self.model = self.config.get("model", "llama3")

    def reload_config(self):
        self._load_config()

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        try:
            if self.provider == "ollama":
                return await self._call_ollama(prompt, system_prompt)
            elif self.provider == "llama_cpp":
                return await self._call_llama_cpp(prompt)
            else:
                return f"Unsupported LLM provider: {self.provider}"
        except Exception as e:
            return f"{self.provider.capitalize()} error: {str(e)}"

    async def _call_ollama(self, prompt: str, system_prompt: Optional[str]) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": { "temperature": self.config.get("temperature", 0.7) }
            }
            if system_prompt:
                payload["prompt"] = f"System: {system_prompt}\n\nUser: {prompt}"
            
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            if response.status_code == 200:
                return response.json().get("response", "").strip()
            return f"Error from Ollama: {response.status_code}"

    async def _call_llama_cpp(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
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
                return response.json().get("content", "").strip()
            return f"Error from llama.cpp: {response.status_code}"
