import os
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class MnemonicConfig(BaseSettings):
    # App Settings
    MNEMONIC_ADMIN_TOKEN: str = "admin-default-secret-change-me"
    
    # Model Settings
    SENTENCE_TRANSFORMER_MODEL: str = "all-MiniLM-L6-v2"
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # Cache Settings
    DATABASE_URI: str = "./data/mnemonic_db"
    CACHE_TABLE_NAME: str = "search_cache"
    CACHE_DISTANCE_THRESHOLD: float = 0.2
    CACHE_REJECTION_THRESHOLD: int = 1
    CACHE_TTL_DAYS: int = 7
    
    # Search Settings
    MAX_RESULTS_PER_ENGINE: int = 100
    
    # Pydantic Settings Config
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @classmethod
    def load(cls):
        # 1. Try config.json
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    data = json.load(f)
                    return cls(**data)
            except Exception as e:
                print(f"Error loading config.json: {e}. Falling back to .env/defaults.")
        
        # 2. Fall back to .env and environment variables
        return cls()

config = MnemonicConfig.load()
