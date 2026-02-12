"""
Models cache service with daily updates.
"""
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
import httpx
from loguru import logger

CACHE_FILE = Path.home() / ".clawlet" / "models_cache.json"
CACHE_DURATION = timedelta(days=1)


class ModelsCache:
    """Cache for provider models with daily updates."""
    
    def __init__(self, cache_file: Path = CACHE_FILE):
        self.cache_file = cache_file
        self._cache: Optional[dict] = None
        self._lock = asyncio.Lock()
    
    async def get_openrouter_models(self, force_refresh: bool = False) -> List[dict]:
        """Get OpenRouter models, fetching from API if cache is expired."""
        async with self._lock:
            if not force_refresh:
                cached = self._load_cache()
                if cached and not self._is_expired(cached):
                    logger.debug("Using cached OpenRouter models")
                    return cached.get("models", [])
            
            # Fetch fresh models
            models = await self._fetch_openrouter_models()
            self._save_cache(models)
            return models
    
    async def _fetch_openrouter_models(self) -> List[dict]:
        """Fetch models from OpenRouter API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"HTTP-Referer": "https://clawlet.ai", "X-Title": "Clawlet"},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract and sort models
            models = data.get("data", [])
            sorted_models = sorted(models, key=lambda x: x.get("id", ""))
            
            logger.info(f"Fetched {len(sorted_models)} models from OpenRouter")
            return sorted_models
    
    def _load_cache(self) -> Optional[dict]:
        """Load cache from disk."""
        if not self.cache_file.exists():
            return None
        
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load models cache: {e}")
            return None
    
    def _save_cache(self, models: List[dict]):
        """Save models to cache."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        cache_data = {
            "updated_at": datetime.utcnow().isoformat(),
            "models": models
        }
        
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
        
        self._cache = cache_data
        logger.info(f"Saved {len(models)} models to cache")
    
    def _is_expired(self, cached: dict) -> bool:
        """Check if cache is expired."""
        updated_at = cached.get("updated_at")
        if not updated_at:
            return True
        
        try:
            updated = datetime.fromisoformat(updated_at)
            return datetime.utcnow() - updated > CACHE_DURATION
        except ValueError:
            return True
    
    def get_cache_info(self) -> Optional[dict]:
        """Get cache information."""
        cached = self._load_cache()
        if not cached:
            return None
        
        updated_at = cached.get("updated_at")
        return {
            "updated_at": updated_at,
            "model_count": len(cached.get("models", [])),
            "is_expired": self._is_expired(cached),
        }


# Global cache instance
_models_cache: Optional[ModelsCache] = None


def get_models_cache() -> ModelsCache:
    """Get global models cache instance."""
    global _models_cache
    if _models_cache is None:
        _models_cache = ModelsCache()
    return _models_cache
