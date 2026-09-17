import httpx
import asyncio
import logging
from typing import Optional, Dict, Any
from functools import wraps

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on_status: Optional[set] = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on_status = retry_on_status or {429, 500, 502, 503, 504}


DEFAULT_RETRY_CONFIG = RetryConfig()


class ResilientHttpClient:
    """HTTP client with configurable timeouts, retries, and exponential backoff."""
    
    def __init__(
        self,
        base_url: str,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
        retry_config: Optional[RetryConfig] = None,
    ):
        self.base_url = base_url
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    connect=self.connect_timeout,
                    read=self.read_timeout,
                    write=self.read_timeout,
                    pool=self.connect_timeout,
                ),
            )
        return self._client
    
    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """Make HTTP request with retry logic."""
        config = self.retry_config
        last_exception = None
        
        for attempt in range(1, config.max_attempts + 1):
            try:
                client = await self._get_client()
                response = await client.request(method, url, **kwargs)
                
                # Check if we should retry based on status code
                if response.status_code in config.retry_on_status and attempt < config.max_attempts:
                    delay = min(
                        config.base_delay * (config.exponential_base ** (attempt - 1)),
                        config.max_delay
                    )
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random())
                    
                    logger.warning(
                        f"Request to {method} {url} failed with status {response.status_code}, "
                        f"retrying in {delay:.2f}s (attempt {attempt}/{config.max_attempts})"
                    )
                    await asyncio.sleep(delay)
                    continue
                
                response.raise_for_status()
                return response
                
            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < config.max_attempts:
                    delay = min(
                        config.base_delay * (config.exponential_base ** (attempt - 1)),
                        config.max_delay
                    )
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random())
                    
                    logger.warning(
                        f"Request to {method} {url} timed out, "
                        f"retrying in {delay:.2f}s (attempt {attempt}/{config.max_attempts})"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
                
            except httpx.ConnectError as e:
                last_exception = e
                if attempt < config.max_attempts:
                    delay = min(
                        config.base_delay * (config.exponential_base ** (attempt - 1)),
                        config.max_delay
                    )
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random())
                    
                    logger.warning(
                        f"Connection error to {method} {url}, "
                        f"retrying in {delay:.2f}s (attempt {attempt}/{config.max_attempts})"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
                
            except httpx.HTTPStatusError as e:
                # Don't retry 4xx errors (except 429)
                if e.response.status_code not in config.retry_on_status:
                    raise
                last_exception = e
                if attempt < config.max_attempts:
                    delay = min(
                        config.base_delay * (config.exponential_base ** (attempt - 1)),
                        config.max_delay
                    )
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random())
                    
                    logger.warning(
                        f"Request to {method} {url} failed with status {e.response.status_code}, "
                        f"retrying in {delay:.2f}s (attempt {attempt}/{config.max_attempts})"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
        
        # If we exhausted retries
        if last_exception:
            raise last_exception
        raise RuntimeError("Max retries exceeded without exception")
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self._request_with_retry("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> httpx.Response:
        return await self._request_with_retry("POST", url, **kwargs)
    
    async def put(self, url: str, **kwargs) -> httpx.Response:
        return await self._request_with_retry("PUT", url, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> httpx.Response:
        return await self._request_with_retry("DELETE", url, **kwargs)


# Pre-configured clients for each external service
def create_ai_client(base_url: str) -> ResilientHttpClient:
    """Create client for AI service - longer timeout for image processing."""
    return ResilientHttpClient(
        base_url=base_url,
        connect_timeout=10.0,
        read_timeout=120.0,  # AI analysis can take time
        retry_config=RetryConfig(max_attempts=3, base_delay=1.0),
    )


def create_decision_client(base_url: str) -> ResilientHttpClient:
    """Create client for Decision Engine - fast response expected."""
    return ResilientHttpClient(
        base_url=base_url,
        connect_timeout=5.0,
        read_timeout=30.0,
        retry_config=RetryConfig(max_attempts=3, base_delay=0.5),
    )


def create_genai_client(base_url: str) -> ResilientHttpClient:
    """Create client for GenAI service - moderate timeout."""
    return ResilientHttpClient(
        base_url=base_url,
        connect_timeout=5.0,
        read_timeout=60.0,
        retry_config=RetryConfig(max_attempts=2, base_delay=1.0),  # Fewer retries for GenAI
    )


def create_weather_client(base_url: str) -> ResilientHttpClient:
    """Create client for Weather service - fast response expected."""
    return ResilientHttpClient(
        base_url=base_url,
        connect_timeout=5.0,
        read_timeout=15.0,
        retry_config=RetryConfig(max_attempts=3, base_delay=0.5),
    )