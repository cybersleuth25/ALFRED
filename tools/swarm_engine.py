import os
import requests
import concurrent.futures

def _fetch_full_url(url: str) -> str:
    """Fetches the full markdown content of a URL using Jina without truncation."""
    try:
        jina_url = f"https://r.jina.ai/{url}"
        resp = requests.get(jina_url, headers={"Accept": "text/event-stream"}, timeout=20)
        resp.raise_for_status()
        return f"--- SOURCE: {url} ---\n{resp.text}\n"
    except Exception as e:
        return f"--- SOURCE: {url} ---\nFailed to fetch: {e}\n"

def deep_research_swarm(topic: str) -> str:
    """
    Spawns concurrent agents to search and scrape massive amounts of data on a topic,
    then uses Gemini 2.5 Flash's massive context window to synthesize a comprehensive report.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Error: GEMINI_API_KEY is not set. The Swarm requires Gemini's massive context window to synthesize data."

    print(f"[Swarm Engine] Initiating Deep Research Swarm for topic: '{topic}'")
    
    # Step 1: Get top 5 search results
    print("[Swarm Engine] Querying DuckDuckGo...")
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(topic, max_results=5))
    except Exception as e:
        return f"Swarm search failed: {e}"
        
    if not results:
        return "The swarm found no search results for this topic."
        
    urls = [r['href'] for r in results if 'href' in r]
    print(f"[Swarm Engine] Found {len(urls)} sources. Unleashing scraping agents...")
    
    # Step 2: Concurrently scrape all URLs
    massive_context = ""
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(_fetch_full_url, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            data = future.result()
            massive_context += data + "\n\n"
            
    print(f"[Swarm Engine] Scraping complete. Synthesizing {len(massive_context)} characters of raw data...")
    
    # Step 3: Synthesize with Gemini
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
You are the Alfred Swarm Synthesizer. A team of AI scraper agents has just returned the following raw data from multiple websites regarding the topic: "{topic}".

Your job is to read through this massive wall of text and write a comprehensive, highly-structured, and incredibly detailed research brief on the topic. 
Include citations referencing the source URLs where applicable.
Format the output beautifully in Markdown.

<RAW_SWARM_DATA>
{massive_context}
</RAW_SWARM_DATA>
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        print("[Swarm Engine] Synthesis complete!")
        return f"**SWARM RESEARCH REPORT: {topic}**\n\n{response.text}"
        
    except Exception as e:
        return f"Swarm synthesis failed: {e}"
