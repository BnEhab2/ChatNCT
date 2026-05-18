from duckduckgo_search import DDGS


def duckduckgo_search_tool(query: str, max_results: int = 5) -> dict:
    """Search the web using DuckDuckGo and return the top results."""
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))

        if not raw_results:
            return {"status": "success", "results": [], "message": "No results found."}

        results = []
        for result in raw_results:
            results.append({
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "snippet": result.get("body", ""),
            })

        return {"status": "success", "results": results}
    except Exception as exc:
        return {"status": "error", "error_message": str(exc)}
