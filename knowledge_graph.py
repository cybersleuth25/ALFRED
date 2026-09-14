"""
Knowledge Graph Engine — Second Brain for Alfred
==================================================
Builds a persistent, local semantic graph of connected entities, concepts,
technologies, people, projects, and preferences from Master Mihir's interactions.

Provides:
  1. Multi-Hop Graph Traversal for complex reasoning.
  2. Automatic Entity & Relation Extraction using fast Groq LLM.
  3. D3.js / Three.js Graph Visualization payload formatting.
  4. Context-aware knowledge retrieval for sub-agents.
"""

import os
import json
import time
import shared
import memory_engine
from datetime import datetime


def add_entity(name: str, entity_type: str = "concept", description: str = "") -> int:
    """Adds or updates an entity node in the knowledge graph."""
    return memory_engine.add_knowledge_node(name, entity_type, description)


def add_relation(source: str, target: str, relation: str, weight: float = 1.0) -> bool:
    """Creates a directed relationship between two entities."""
    return memory_engine.add_knowledge_edge(source, target, relation, weight)


def query_subgraph(entity_name: str, depth: int = 2) -> dict:
    """
    Performs multi-hop graph traversal starting from an entity.
    Returns connected nodes and relationships up to `depth` hops.
    """
    return memory_engine.get_node_subgraph(entity_name, depth)


def get_graph_data() -> dict:
    """
    Returns graph nodes and edges formatted for D3.js / Three.js force-directed visualization.
    Schema:
      {
        "nodes": [{"id": 1, "name": "Python", "type": "tech", "val": 5}, ...],
        "links": [{"source": 1, "target": 2, "relation": "USES", "weight": 1.0}, ...]
      }
    """
    nodes = memory_engine.get_all_knowledge_nodes()
    edges = memory_engine.get_all_knowledge_edges()

    # Calculate degree / node size based on number of connections
    degree_map = {}
    for e in edges:
        s_id = e["source_id"]
        t_id = e["target_id"]
        degree_map[s_id] = degree_map.get(s_id, 0) + 1
        degree_map[t_id] = degree_map.get(t_id, 0) + 1

    formatted_nodes = []
    for n in nodes:
        formatted_nodes.append({
            "id": n["id"],
            "name": n["name"],
            "type": n["entity_type"],
            "description": n.get("description", ""),
            "connections": degree_map.get(n["id"], 0),
            "created_at": n["created_at"],
            "updated_at": n["updated_at"]
        })

    formatted_links = []
    for e in edges:
        formatted_links.append({
            "id": e["id"],
            "source": e["source_id"],
            "target": e["target_id"],
            "source_name": e.get("source_name", ""),
            "target_name": e.get("target_name", ""),
            "relation": e["relation"],
            "weight": e.get("weight", 1.0)
        })

    return {
        "nodes": formatted_nodes,
        "links": formatted_links,
        "total_nodes": len(formatted_nodes),
        "total_edges": len(formatted_links)
    }


def extract_and_link_from_text(text: str) -> dict:
    """
    Uses LLM to extract entities and triples (Subject -> Relation -> Object)
    from conversation turns, notes, or facts, and automatically stores them in the graph.
    """
    if not text or len(text.strip()) < 5:
        return {"entities": 0, "relations": 0}

    client, model = shared.get_brain()
    if not client:
        return {"error": "LLM client not available"}

    system_prompt = """You are Alfred's Knowledge Graph Extractor.
Extract key entities (people, technologies, projects, places, preferences, concepts) and their relationships from the user's text.
Output ONLY valid raw JSON with NO markdown formatting or codeblocks.

Schema:
{
  "entities": [
    {"name": "Entity Name", "type": "person|tech|project|place|preference|concept", "description": "brief info"}
  ],
  "relations": [
    {"source": "Entity Name", "target": "Other Entity", "relation": "WORKS_ON|USES|LOCATED_IN|PREFERS|CREATED|PART_OF|INTERESTED_IN"}
  ]
}

Rules:
1. Normalize names (e.g. 'Python', 'VS Code', 'Mihir').
2. Relations should be uppercase with underscores.
3. If no clear entities/relations exist, output {"entities": [], "relations": []}.
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Text to extract from: {text}"}
            ],
            temperature=0.1,
            max_tokens=1500
        )
        raw = response.choices[0].message.content.strip()
        import re
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            data = json.loads(raw)

        entities_added = 0
        relations_added = 0

        # Save entities
        for ent in data.get("entities", []):
            name = ent.get("name") or ent.get("text")
            if name and str(name).strip():
                add_entity(
                    name=str(name).strip(),
                    entity_type=ent.get("type", "concept"),
                    description=ent.get("description", "")
                )
                entities_added += 1

        # Save relations
        for rel in data.get("relations", []):
            if "source" in rel and "target" in rel and "relation" in rel:
                s = rel["source"].strip()
                t = rel["target"].strip()
                r = rel["relation"].strip()
                if s and t and r:
                    add_relation(s, t, r)
                    relations_added += 1

        if entities_added > 0 or relations_added > 0:
            print(f"[Knowledge Graph] Extracted {entities_added} entities, {relations_added} relations from text.")

        return {"entities": entities_added, "relations": relations_added}

    except Exception as e:
        print(f"[Knowledge Graph] Extraction error: {e}")
        return {"error": str(e)}


def query_knowledge_summary(query: str) -> str:
    """
    Finds entities matching words in query, retrieves their subgraphs,
    and returns a structured text summary for agent reasoning.
    """
    nodes = memory_engine.get_all_knowledge_nodes()
    query_lower = query.lower()

    matched_nodes = []
    for n in nodes:
        if n["name"].lower() in query_lower:
            matched_nodes.append(n)

    if not matched_nodes:
        return ""

    summary_lines = ["KNOWLEDGE GRAPH CONTEXT (Connected Entities):"]
    for node in matched_nodes[:3]:
        subgraph = query_subgraph(node["name"], depth=1)
        neighbors = []
        for e in subgraph.get("edges", []):
            if e["source_name"].lower() == node["name"].lower():
                neighbors.append(f"{node['name']} --[{e['relation']}]--> {e['target_name']}")
            else:
                neighbors.append(f"{e['source_name']} --[{e['relation']}]--> {node['name']}")
        
        if neighbors:
            summary_lines.append(f"• {node['name']} ({node['entity_type']}): " + "; ".join(neighbors))
        else:
            summary_lines.append(f"• {node['name']} ({node['entity_type']})")

    return "\n".join(summary_lines)
