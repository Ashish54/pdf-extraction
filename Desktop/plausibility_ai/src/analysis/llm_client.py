import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential
from ..config import Config
import logging
from typing import List, Tuple, Any

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
    # pyrefly: ignore [missing-import]
    import httpx
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None
    httpx = None

from ..auth_client import AuthClientWrapper

class LLMClient:
    """Client for OpenAI-compatible LLM APIs."""
    
    def __init__(self, config: Config):
        self.endpoint = config.llm.endpoint
        self.model_name = config.llm.model_name
        self.temperature = config.llm.temperature
        self.max_tokens = config.llm.max_output_tokens
        self.timeout = config.llm.timeout_seconds
        self.max_retries = config.llm.max_retries
        # Use httpx AsyncClient for concurrent requests
        self.client = httpx.AsyncClient(timeout=self.timeout)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    async def analyze(self, user_prompt: str, system_prompt: str) -> str:
        """Send a single analysis request to the LLM."""
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            # If the self-hosted model supports JSON mode natively, uncomment below:
            # "response_format": {"type": "json_object"}
        }

        try:
            response = await self.client.post(self.endpoint, json=payload)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except httpx.HTTPError as e:
            logger.error(f"HTTP Error calling LLM API: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling LLM API: {e}")
            raise

    async def analyze_batch(self, prompts: List[Tuple[str, str]], max_concurrent: int = 5) -> List[Any]:
        """
        Analyze multiple prompts concurrently, respecting concurrency limits.
        prompts is a list of (system_prompt, user_prompt) tuples.
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def bounded_analyze(system: str, user: str) -> Any:
            async with semaphore:
                try:
                    return await self.analyze(user, system)
                except Exception as e:
                    return e

        tasks = [bounded_analyze(sys, usr) for sys, usr in prompts]
        return await asyncio.gather(*tasks, return_exceptions=True)
        
    async def close(self):
        await self.client.aclose()
