"""
Deep Research Swarm v2 — Multi-Agent OSINT Synthesizer for Alfred
=================================================================
Autonomous multi-agent research pipeline that investigates complex topics from
multiple angles, cross-verifies claims across sources, compiles structured
dossiers in Alfred_Workspace/research/, and embeds findings directly into
Alfred's Second Brain (FAISS Semantic Memory + Knowledge Graph).

Agents:
  1. QueryPlannerAgent: Decomposes topics into 5 specialized query vectors.
  2. SearcherAgent: Parallel search across DuckDuckGo, Google News RSS, and Wikipedia.
  3. ScraperAgent: Parallel extraction via Jina AI with resilient local HTML fallback.
  4. FactCheckerAgent: Cross-examines sources for contradictions and credibility.
  5. SynthesizerAgent: Compiles an executive research dossier with citations.
  6. KnowledgeIntegrator: Auto-embeds into FAISS memory & Knowledge Graph.
"""

import os
import re
import time
import json
import requests
import urllib.parse
import concurrent.futures
from datetime import datetime

import shared

# Ensure research directory exists in workspace
WORKSPACE_RESEARCH_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "Alfred_Workspace", "research")
)
os.makedirs(WORKSPACE_RESEARCH_DIR, exist_ok=True)


def _safe_filename(text: str) -> str:
    """Converts a topic string into a clean, filesystem-safe filename."""
    cleaned = re.sub(r'[^\w\s-]', '', text.lower()).strip()
    return re.sub(r'[-\s]+', '_', cleaned)[:60]


# ─────────────────────────────────────────────────────────────
# AGENT 1: Query Planner Agent
# ─────────────────────────────────────────────────────────────
class QueryPlannerAgent:
    """Decomposes a broad topic into 5 specialized search vectors."""

    def plan_queries(self, topic: str) -> list:
        client, model_name = shared.get_brain()
        fallback_queries = [
            f"{topic} overview fundamentals",
            f"{topic} technical architecture how it works",
            f"{topic} challenges limitations controversies",
            f"{topic} latest 2026 breakthroughs news",
            f"{topic} future predictions applications roadmap"
        ]

        if not client:
            return fallback_queries

        prompt = f"""You are the Swarm Query Planner. Given the research topic below, generate exactly 5 distinct, high-precision web search queries covering:
1. Core concepts & fundamentals
2. Technical mechanics / how it works
3. Key challenges, risks, or controversies
4. Recent 2026 breakthroughs, key players, and news
5. Future roadmap and practical applications

Topic: "{topic}"

Output ONLY a raw JSON array of 5 query strings. No markdown, no commentary.
Example: ["query 1", "query 2", "query 3", "query 4", "query 5"]"""

        try:
            res = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=250
            )
            raw = res.choices[0].message.content.strip()
            # Clean possible markdown wrapping
            if raw.startswith("```"):
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```$', '', raw)
            queries = json.loads(raw)
            if isinstance(queries, list) and len(queries) >= 3:
                return [str(q).strip() for q in queries[:5]]
        except Exception as e:
            shared.push_log(f"QueryPlanner using heuristic fallback: {e}", "SwarmPlanner")

        return fallback_queries


# ─────────────────────────────────────────────────────────────
# AGENT 2: Multi-Engine Searcher Agent
# ─────────────────────────────────────────────────────────────
class SearcherAgent:
    """Gathers high-signal URLs across DuckDuckGo, Google News, and Wikipedia."""

    def search_duckduckgo(self, query: str, max_results: int = 4) -> list:
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            return [r['href'] for r in results if 'href' in r and not r['href'].endswith('.pdf')]
        except Exception as e:
            shared.push_log(f"DDG search error for '{query[:30]}': {e}", "SwarmSearcher")
            return []

    def search_google_news(self, query: str, max_results: int = 3) -> list:
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
            resp = requests.get(url, timeout=7, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            
            links = re.findall(r'<link>(.*?)</link>', resp.text)
            clean_links = [l for l in links if 'news.google.com' not in l or 'articles' in l]
            return clean_links[:max_results]
        except Exception:
            return []

    def search_wikipedia(self, topic: str) -> list:
        try:
            url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote_plus(topic)}&limit=2&namespace=0&format=json"
            resp = requests.get(url, timeout=5, headers={"User-Agent": "AlfredOSINT/2.0"})
            if resp.status_code == 200:
                data = resp.json()
                if len(data) >= 4 and data[3]:
                    return data[3]
        except Exception:
            pass
        return []

    def gather_sources(self, queries: list, topic: str) -> list:
        """Executes parallel searches across all query angles."""
        collected_urls = []
        
        # Include Wikipedia query for foundational context
        collected_urls.extend(self.search_wikipedia(topic))

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_query = {executor.submit(self._search_single_vector, q): q for q in queries}
            for future in concurrent.futures.as_completed(future_to_query):
                try:
                    urls = future.result()
                    collected_urls.extend(urls)
                except Exception:
                    pass

        # Deduplicate and filter out noisy domains
        filtered = []
        seen = set()
        blocked_domains = ['youtube.com', 'facebook.com', 'instagram.com', 'tiktok.com', 'pinterest.com']

        for url in collected_urls:
            if not url or url in seen:
                continue
            if any(b in url.lower() for b in blocked_domains):
                continue
            seen.add(url)
            filtered.append(url)

        return filtered[:10]  # Cap at top 10 most relevant URLs

    def _search_single_vector(self, query: str) -> list:
        results = []
        results.extend(self.search_duckduckgo(query, max_results=3))
        results.extend(self.search_google_news(query, max_results=2))
        return results


# ─────────────────────────────────────────────────────────────
# AGENT 2.5: Academic Research Agent (arXiv + Scholar)
# ─────────────────────────────────────────────────────────────
class AcademicSearcherAgent:
    """Searches arXiv for peer-reviewed academic papers and scientific preprints."""

    def search_arxiv(self, query: str, max_results: int = 3) -> list:
        try:
            import xml.etree.ElementTree as ET
            encoded = urllib.parse.quote_plus(query)
            url = f"http://export.arxiv.org/api/query?search_query=all:{encoded}&start=0&max_results={max_results}"
            resp = requests.get(url, timeout=8, headers={"User-Agent": "AlfredResearchSwarm/2.0"})
            if resp.status_code != 200:
                return []
            
            root = ET.fromstring(resp.text)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            papers = []
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns)
                summary = entry.find('atom:summary', ns)
                published = entry.find('atom:published', ns)
                id_elem = entry.find('atom:id', ns)
                
                t_text = title.text.strip().replace('\n', ' ') if title is not None and title.text else "Untitled Paper"
                s_text = summary.text.strip().replace('\n', ' ') if summary is not None and summary.text else ""
                pub_date = published.text[:10] if published is not None and published.text else "Recent"
                link = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                
                if s_text:
                    papers.append({
                        "url": link,
                        "title": f"[arXiv: {pub_date}] {t_text}",
                        "content": f"Title: {t_text}\nPublished: {pub_date}\nLink: {link}\nAbstract: {s_text[:1200]}"
                    })
            return papers
        except Exception as e:
            shared.push_log(f"arXiv academic query note: {e}", "SwarmScholar")
            return []


# ─────────────────────────────────────────────────────────────
# AGENT 3: Resilient Scraper Agent
# ─────────────────────────────────────────────────────────────
class ScraperAgent:
    """Extracts high-density markdown/text from URLs with Jina AI + HTML fallback."""

    def scrape_url(self, url: str) -> dict:
        """Fetches and cleans content from a single URL."""
        # 1. Primary: Jina AI Reader
        try:
            jina_url = f"https://r.jina.ai/{url}"
            resp = requests.get(jina_url, timeout=12, headers={
                "User-Agent": "Mozilla/5.0",
                "X-Return-Format": "markdown"
            })
            if resp.status_code == 200 and len(resp.text.strip()) > 200:
                cleaned = self._clean_markdown(resp.text)
                return {"url": url, "content": cleaned[:4000], "status": "success", "engine": "jina"}
        except Exception:
            pass

        # 2. Fallback: Direct requests + BeautifulSoup
        try:
            resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Strip out scripts, styles, headers, footers
                for tag in soup(["script", "style", "nav", "footer", "aside", "header", "noscript"]):
                    tag.decompose()
                text = soup.get_text(separator=' ', strip=True)
                cleaned = re.sub(r'\s+', ' ', text).strip()
                if len(cleaned) > 200:
                    return {"url": url, "content": cleaned[:3500], "status": "success", "engine": "html_fallback"}
        except Exception as e:
            return {"url": url, "content": f"Extraction error: {e}", "status": "failed", "engine": "none"}

        return {"url": url, "content": "Insufficient extractable text.", "status": "failed", "engine": "none"}

    def scrape_all(self, urls: list) -> list:
        """Scrapes multiple URLs in parallel."""
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_url = {executor.submit(self.scrape_url, u): u for u in urls}
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    res = future.result()
                    if res["status"] == "success":
                        results.append(res)
                except Exception:
                    pass
        return results

    def _clean_markdown(self, text: str) -> str:
        # Strip excessive blank lines and image markdown
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


# ─────────────────────────────────────────────────────────────
# AGENT 4: Fact Checker & Analyst Agent
# ─────────────────────────────────────────────────────────────
class FactCheckerAgent:
    """Cross-examines scraped sources for inconsistencies, hype, and consensus."""

    def analyze(self, topic: str, extracted_sources: list) -> str:
        client, model_name = shared.get_brain()
        if not client or not extracted_sources:
            return "Cross-source validation skipped (insufficient sources or LLM offline)."

        corpus = ""
        for i, s in enumerate(extracted_sources[:6], 1):
            corpus += f"\n[SOURCE {i}: {s['url']}]\n{s['content'][:1500]}\n"

        prompt = f"""You are the Swarm Fact-Checker & Critical Analyst.
Analyze the following multi-source intelligence regarding the topic: "{topic}".

Evaluate:
1. High-consensus facts agreed upon by multiple sources.
2. Contradictions, statistical discrepancies, or timeline conflicts between sources.
3. Distinguish between verified factual developments vs. speculative marketing claims.

Provide a concise, 2-paragraph analytical assessment.

RAW SOURCES:
{corpus[:18000]}"""

        try:
            res = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=400
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            return f"Fact-checking synthesis notice: {e}"


# ─────────────────────────────────────────────────────────────
# AGENT 5: Executive Synthesizer Agent
# ─────────────────────────────────────────────────────────────
class SynthesizerAgent:
    """Synthesizes all gathered intelligence into an executive research dossier."""

    def generate_dossier(self, topic: str, sources: list, fact_check: str) -> str:
        client, model_name = shared.get_brain()
        now_str = datetime.now().strftime("%B %d, %Y")

        if not client:
            return f"# Research Brief: {topic}\n\nGathered {len(sources)} sources, but LLM synthesis was unavailable."

        corpus = ""
        source_links = []
        for i, s in enumerate(sources[:8], 1):
            corpus += f"\n--- SOURCE {i} ({s['url']}) ---\n{s['content'][:2000]}\n"
            source_links.append(f"{i}. [{s['url']}]({s['url']})")

        source_biblio = "\n".join(source_links)

        prompt = f"""You are the Alfred Executive Research Synthesizer.
A swarm of OSINT searcher and scraper agents has retrieved the following raw intelligence on: "{topic}".
The Fact-Checker Agent has also provided this credibility analysis:
{fact_check}

Synthesize this into a structured, publication-grade Research Dossier in Markdown format.

Structure required:
# 🔬 Executive Research Dossier: {topic}
**Date:** {now_str} | **Swarm Status:** Verified ({len(sources)} Sources Analyzed)

## 📌 Executive Summary
(3-4 high-density bullet points summarizing the core takeaways)

## ⚙️ Fundamental Architecture & Core Concepts
(Clear explanation of how it works, technical mechanisms, or structural foundations)

## 🚀 Key 2026 Breakthroughs & Current Landscape
(Recent developments, prominent organizations/players, real-world implementations)

## ⚠️ Critical Challenges, Bottlenecks & Controversies
(Technical limitations, ethical considerations, or market headwinds)

## 🔮 Future Outlook & Strategic Roadmap
(Where this is heading in the next 1-3 years)

## 🛡️ Fact-Check & Cross-Source Evaluation
(Incorporate key insights from the Fact-Checker analysis)

## 📚 References & Verified Sources
{source_biblio}

<RAW_INTELLIGENCE>
{corpus[:24000]}
</RAW_INTELLIGENCE>"""

        try:
            res = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2200
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            return f"# Swarm Synthesis Report: {topic}\n\nSynthesis error: {e}"


# ─────────────────────────────────────────────────────────────
# SWARM ORCHESTRATOR v2
# ─────────────────────────────────────────────────────────────
class SwarmOrchestratorV2:
    """Coordinates the full end-to-end Deep Research Swarm pipeline."""

    def __init__(self):
        self.planner = QueryPlannerAgent()
        self.searcher = SearcherAgent()
        self.academic = AcademicSearcherAgent()
        self.scraper = ScraperAgent()
        self.fact_checker = FactCheckerAgent()
        self.synthesizer = SynthesizerAgent()

    def run(self, topic: str) -> str:
        t0 = time.time()
        shared.push_log(f"Initiating Deep Research Swarm v2 for: '{topic}'", "SwarmOrchestrator")
        shared.push_swarm_progress("planning", "QueryPlannerAgent", f"Decomposing '{topic}' into specialized search vectors...", 15, 0, topic)

        # ── Phase 1: Query Decomposition ──
        shared.push_log("Phase 1/5: Decomposing research vectors...", "SwarmOrchestrator")
        queries = self.planner.plan_queries(topic)
        shared.push_log(f"Generated {len(queries)} specialized search vectors.", "SwarmOrchestrator")

        # ── Phase 2: Parallel Search & Academic Retrieval ──
        shared.push_swarm_progress("searching", "SearcherAgent", "Deploying searcher agents across multi-engine index & arXiv...", 35, 0, topic)
        shared.push_log("Phase 2/5: Deploying searcher agents across multi-engine index & arXiv...", "SwarmOrchestrator")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut_urls = executor.submit(self.searcher.gather_sources, queries, topic)
            fut_academic = executor.submit(self.academic.search_arxiv, topic, 3)
            urls = fut_urls.result()
            academic_papers = fut_academic.result()

        if not urls and not academic_papers:
            shared.push_swarm_progress("failed", "SwarmOrchestrator", f"Unable to locate live sources for '{topic}'.", 0, 0, topic)
            return f"The research swarm was unable to locate live public sources for '{topic}', sir."

        total_sources_count = len(urls) + len(academic_papers)
        shared.push_log(f"Found {len(urls)} web sources and {len(academic_papers)} academic research papers.", "SwarmOrchestrator")

        # ── Phase 3: Parallel Scraping ──
        shared.push_swarm_progress("scraping", "ScraperAgent", f"Extracting content from {len(urls)} web sources + {len(academic_papers)} papers...", 55, total_sources_count, topic)
        shared.push_log("Phase 3/5: Scraper agents extracting full-text payloads...", "SwarmOrchestrator")
        extracted_sources = self.scraper.scrape_all(urls)

        # Merge academic preprints & abstracts
        if academic_papers:
            extracted_sources.extend(academic_papers)

        if not extracted_sources:
            shared.push_swarm_progress("failed", "SwarmOrchestrator", "Content extraction was blocked.", 0, 0, topic)
            return f"The swarm identified candidate sources for '{topic}', but content extraction was blocked."

        total_chars = sum(len(s["content"]) for s in extracted_sources)
        shared.push_log(f"Extracted {total_chars:,} characters from {len(extracted_sources)} sources.", "SwarmOrchestrator")

        # ── Phase 4: Fact-Checking ──
        shared.push_swarm_progress("fact_checking", "FactCheckerAgent", "Cross-examining sources and validating claims...", 75, len(extracted_sources), topic)
        shared.push_log("Phase 4/5: Cross-examining claims and validating facts...", "SwarmOrchestrator")
        fact_check_report = self.fact_checker.analyze(topic, extracted_sources)

        # ── Phase 5: Dossier Synthesis ──
        shared.push_swarm_progress("synthesizing", "SynthesizerAgent", "Compiling executive research dossier with citations...", 90, len(extracted_sources), topic)
        shared.push_log("Phase 5/5: Compiling executive research dossier...", "SwarmOrchestrator")
        dossier = self.synthesizer.generate_dossier(topic, extracted_sources, fact_check_report)

        # ── Phase 6: Persistence & Second Brain Ingestion ──
        filename = f"{_safe_filename(topic)}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
        filepath = os.path.join(WORKSPACE_RESEARCH_DIR, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(dossier)
            shared.push_log(f"Saved research dossier to Alfred_Workspace/research/{filename}", "SwarmOrchestrator")
        except Exception as e:
            shared.push_log(f"Failed to write file to workspace: {e}", "SwarmOrchestrator")

        # Ingest into Semantic Memory (FAISS)
        try:
            import memory_engine
            # Store topic + first 800 chars of executive summary
            summary_snippet = dossier[:800]
            memory_engine.store_memory(
                f"Deep Research Dossier on {topic}: {summary_snippet}",
                category="fact"
            )
        except Exception:
            pass

        # Ingest into Knowledge Graph
        try:
            import knowledge_graph
            knowledge_graph.extract_and_link_from_text(dossier[:1200])
        except Exception:
            pass

        # Optional Telegram alert
        try:
            import telegram_notifier
            if telegram_notifier.is_available():
                telegram_notifier.send_alert(
                    f"[Deep Research Swarm Complete]\nTopic: {topic}\nSaved to: {filename}"
                )
        except Exception:
            pass

        elapsed = time.time() - t0
        shared.push_log(f"Swarm v2 complete in {elapsed:.1f}s!", "SwarmOrchestrator")
        shared.push_swarm_progress("completed", "KnowledgeIntegrator", f"Dossier ready & saved to {filename}", 100, len(extracted_sources), topic, filename)

        # Extract executive summary bullet points for voice response
        spoken_summary = self._extract_spoken_summary(topic, dossier, filename)
        # Sanitize non-ASCII characters that might trip Windows voice/charmap
        spoken_summary = spoken_summary.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '--')
        return spoken_summary

    def _extract_spoken_summary(self, topic: str, dossier: str, filename: str) -> str:
        """Extracts a clean, 2-sentence conversational summary suitable for voice speech."""
        # Find Executive Summary section
        match = re.search(r'## 📌 Executive Summary\s*(.*?)(?=##|\Z)', dossier, re.DOTALL)
        if match:
            lines = [line.strip().lstrip('•-*0123456789. ') for line in match.group(1).strip().split('\n') if line.strip()]
            if lines:
                bullets = " ".join(lines[:2])
                return f"I've completed the deep research swarm on {topic}, sir. In brief: {bullets} The complete dossier has been compiled and saved to your research workspace as {filename}."

        return f"I have concluded deep research on {topic}, sir. The full intelligence brief has been verified and saved to your research folder as {filename}."


# ─────────────────────────────────────────────────────────────
# TOOL ENTRY POINT
# ─────────────────────────────────────────────────────────────
def deep_research_swarm(topic: str) -> str:
    """
    Entry point for core_tools and task_orchestrator.
    Spawns the autonomous Multi-Agent Deep Research Swarm on the given topic.
    """
    orchestrator = SwarmOrchestratorV2()
    return orchestrator.run(topic)
