"""
Web search tool using Brave Search API.
"""

import asyncio
from typing import Optional
from dataclasses import dataclass

import httpx

from clawlet.tools.registry import BaseTool, ToolResult
from loguru import logger


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    description: str
    
    def to_markdown(self) -> str:
        return f"- [{self.title}]({self.url})\n  {self.description}"


class WebSearchTool(BaseTool):
    """
    Tool for searching the web using Brave Search API.
    
    Get your free API key at: https://brave.com/search/api/
    """
    
    API_URL = "https://api.search.brave.com/res/v1/web/search"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        max_results: int = 5,
        timeout: float = 10.0,
    ):
        """
        Initialize web search tool.
        
        Args:
            api_key: Brave Search API key
            max_results: Maximum results to return
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.max_results = max_results
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        
        if api_key:
            logger.info(f"WebSearchTool initialized with API key (max_results={max_results})")
        else:
            logger.warning("WebSearchTool initialized WITHOUT API key - searches will fail")
    
    async def __aenter__(self) -> "WebSearchTool":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - cleanup resources."""
        await self.close()
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return """Search the web for information.
        Returns titles, URLs, and descriptions of relevant pages.
        Use this to find current information, news, or research topics."""
    
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of results (default: 5)",
                },
            },
            "required": ["query"],
        }
    
    async def execute(self, query: str, count: Optional[int] = None, **kwargs) -> ToolResult:
        """
        Execute a web search.
        
        Args:
            query: Search query
            count: Number of results (overrides default)
            
        Returns:
            ToolResult with formatted search results
        """
        if not self.api_key:
            return ToolResult(
                success=False,
                output="",
                error="Brave Search API key not configured. Set WEB_SEARCH_API_KEY or BRAVE_SEARCH_API_KEY environment variable, or configure in config.yaml."
            )
        
        count = count or self.max_results
        
        try:
            # Initialize client if needed
            if self._client is None:
                self._client = httpx.AsyncClient(timeout=self.timeout)
            
            # Make request
            response = await self._client.get(
                self.API_URL,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self.api_key,
                },
                params={
                    "q": query,
                    "count": count,
                }
            )
            
            if response.status_code == 401:
                return ToolResult(
                    success=False,
                    output="",
                    error="Invalid API key for Brave Search"
                )
            
            if response.status_code == 429:
                return ToolResult(
                    success=False,
                    output="",
                    error="Brave Search rate limit exceeded"
                )
            
            response.raise_for_status()
            
            # Parse results
            data = response.json()
            results = self._parse_results(data)
            
            if not results:
                return ToolResult(
                    success=True,
                    output="No results found.",
                    data={"query": query, "results": []}
                )
            
            # Format output
            output_lines = [f"## Search: {query}\n"]
            for i, result in enumerate(results, 1):
                output_lines.append(f"**{i}. {result.title}**")
                output_lines.append(f"   {result.url}")
                output_lines.append(f"   {result.description}\n")
            
            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                data={
                    "query": query,
                    "results": [
                        {
                            "title": r.title,
                            "url": r.url,
                            "description": r.description,
                        }
                        for r in results
                    ]
                }
            )
            
        except httpx.TimeoutException:
            return ToolResult(
                success=False,
                output="",
                error="Search request timed out"
            )
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Search failed: {str(e)}"
            )
    
    def _parse_results(self, data: dict) -> list[SearchResult]:
        """Parse Brave Search API response."""
        results = []
        
        # Navigate to web results
        web_data = data.get("web", {})
        web_results = web_data.get("results", [])
        
        for item in web_results:
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            description = item.get("description", "")
            
            if url:  # Only include if we have a URL
                results.append(SearchResult(
                    title=title,
                    url=url,
                    description=description,
                ))
        
        return results
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
