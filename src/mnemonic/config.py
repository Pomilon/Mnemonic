import os
import json
import shutil
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Any, Dict

def ensure_config_exists(path: str):
    """If a config file doesn't exist, try to copy its .example version."""
    if not os.path.exists(path):
        example_path = path + ".example"
        if os.path.exists(example_path):
            print(f"Config: {path} not found. Initializing from example.")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            shutil.copy2(example_path, path)
        else:
            # Create a directory if it doesn't exist for new files
            os.makedirs(os.path.dirname(path), exist_ok=True)

class SystemConfig(BaseSettings):
    """Sensitive settings loaded ONLY from .env or environment variables."""
    MNEMONIC_ADMIN_TOKEN: str = "admin-default-secret-change-me"
    
    # API Keys (Static System Config)
    BRAVE_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_CSE_ID: Optional[str] = None
    BING_API_KEY: Optional[str] = None
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

class ConfigManager:
    """Manages application-level settings stored in JSON."""
    def __init__(self):
        self.system = SystemConfig()
        self.app_path = os.path.join(os.path.dirname(__file__), "aggregator", "app_config.json")
        ensure_config_exists(self.app_path)
        self.app: Dict[str, Any] = self._load_app_config()

    def _load_app_config(self) -> Dict[str, Any]:
        defaults = {
            "SENTENCE_TRANSFORMER_MODEL": "all-MiniLM-L6-v2",
            "DATABASE_URI": "./data/mnemonic_db",
            "CACHE_TABLE_NAME": "search_cache",
            "CACHE_DISTANCE_THRESHOLD": 0.2,
            "CACHE_REJECTION_THRESHOLD": 1,
            "CACHE_TTL_DAYS": 7,
            "MAX_RESULTS_PER_ENGINE": 100,
            "RECALIBRATION_ALPHA": 0.15,
            "REJECTION_PENALTY_WEIGHT": 0.3,
            "USE_HYDE": True
        }
        if os.path.exists(self.app_path):
            try:
                with open(self.app_path, "r") as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception as e:
                print(f"Error loading app_config.json: {e}")
        return defaults

    def save_app_config(self, new_config: Dict[str, Any]):
        self.app.update(new_config)
        os.makedirs(os.path.dirname(self.app_path), exist_ok=True)
        with open(self.app_path, "w") as f:
            json.dump(self.app, f, indent=2)

    # Proxy properties for backward compatibility
    @property
    def MNEMONIC_ADMIN_TOKEN(self): return self.system.MNEMONIC_ADMIN_TOKEN
    @property
    def BRAVE_API_KEY(self): return self.system.BRAVE_API_KEY
    @property
    def GOOGLE_API_KEY(self): return self.system.GOOGLE_API_KEY
    @property
    def GOOGLE_CSE_ID(self): return self.system.GOOGLE_CSE_ID
    @property
    def BING_API_KEY(self): return self.system.BING_API_KEY

    @property
    def SENTENCE_TRANSFORMER_MODEL(self): return self.app.get("SENTENCE_TRANSFORMER_MODEL")
    @property
    def DATABASE_URI(self): return self.app.get("DATABASE_URI")
    @property
    def CACHE_TABLE_NAME(self): return self.app.get("CACHE_TABLE_NAME")
    @property
    def CACHE_DISTANCE_THRESHOLD(self): return self.app.get("CACHE_DISTANCE_THRESHOLD")
    @property
    def CACHE_REJECTION_THRESHOLD(self): return self.app.get("CACHE_REJECTION_THRESHOLD")
    @property
    def CACHE_TTL_DAYS(self): return self.app.get("CACHE_TTL_DAYS")
    @property
    def MAX_RESULTS_PER_ENGINE(self): return self.app.get("MAX_RESULTS_PER_ENGINE")
    @property
    def RECALIBRATION_ALPHA(self): return self.app.get("RECALIBRATION_ALPHA")
    @property
    def REJECTION_PENALTY_WEIGHT(self): return self.app.get("REJECTION_PENALTY_WEIGHT")
    @property
    def USE_HYDE(self): return self.app.get("USE_HYDE")
    
    # Provider-specific config (should use llm_config.json but kept for compat)
    @property
    def OLLAMA_BASE_URL(self): return "http://localhost:11434"
    @property
    def OLLAMA_MODEL(self): return "llama3"

# Initialize global config
config = ConfigManager()
