import sqlite3
import os
import json
import math
import numpy as np
from datetime import datetime

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

DB_PATH = os.path.join(os.path.dirname(__file__), "alfred_memory.db")

# --- Embedding Configuration ---
EMBED_MODEL = "nomic-embed-text"

def _get_connection():
    """Returns a SQLite connection."""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initialize the database and ensure tables exist."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    # Create Tasks/Reminders table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            added_at TEXT NOT NULL,
            completed BOOLEAN NOT NULL CHECK (completed IN (0, 1)),
            deadline TEXT
        )
    """)
    
    # Create User Facts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact TEXT NOT NULL,
            added_at TEXT NOT NULL
        )
    """)
    
    # Create System Logs table (useful for debugging Phase 4 & 5)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_level TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    
    # --- NEW: Semantic Memory Table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semantic_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            embedding TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            created_at TEXT NOT NULL
        )
    """)
    
    # --- NEW: Persistent Conversation History ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    # --- NEW: User Profiles for Multi-User Support ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    # Ensure default user exists
    default_name = os.getenv("ALFRED_USER_NAME", "User")
    cursor.execute(
        "INSERT OR IGNORE INTO user_profiles (id, telegram_id, display_name, created_at) VALUES (1, ?, ?, ?)",
        (os.getenv('TELEGRAM_ALLOWED_USER_ID', ''), default_name, datetime.now().isoformat())
    )
    
    # Add user_id column to user_facts if it doesn't exist
    try:
        cursor.execute("ALTER TABLE user_facts ADD COLUMN user_id INTEGER DEFAULT 1")
    except Exception:
        pass  # Column already exists
    
    # Add user_id column to semantic_memories if it doesn't exist
    try:
        cursor.execute("ALTER TABLE semantic_memories ADD COLUMN user_id INTEGER DEFAULT 1")
    except Exception:
        pass  # Column already exists
    
    conn.commit()
    conn.close()

# =============================================
# ORIGINAL FUNCTIONS (Unchanged)
# =============================================

def add_task(task: str, deadline: str = None):
    """Adds a new task to the database."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (task, added_at, completed, deadline) VALUES (?, ?, ?, ?)",
        (task, datetime.now().isoformat(), 0, deadline)
    )
    conn.commit()
    conn.close()

def get_pending_tasks() -> list:
    """Returns a list of dicts for pending tasks."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, task, added_at, deadline FROM tasks WHERE completed = 0")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row["id"], "task": row["task"], "added_at": row["added_at"], "deadline": row["deadline"]} for row in rows]

def get_due_tasks() -> list:
    """Returns a list of tasks that have a deadline which has already passed, and are not yet completed."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Check if deadline is not null and is <= current time
    cursor.execute("SELECT id, task, added_at, deadline FROM tasks WHERE completed = 0 AND deadline IS NOT NULL AND deadline <= ?", (datetime.now().isoformat(),))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row["id"], "task": row["task"], "added_at": row["added_at"], "deadline": row["deadline"]} for row in rows]

def complete_task(task_id: int):
    """Marks a task as completed."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET completed = 1 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

def delete_task(task_id: int):
    """Permanently deletes a task from the database."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

def clear_all_tasks():
    """Permanently deletes all tasks from the database."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()

def log_system_event(level: str, message: str):
    """Logs a system event to SQLite."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO system_logs (log_level, message, timestamp) VALUES (?, ?, ?)",
        (level, message, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def add_user_fact(fact: str):
    """Adds a permanent fact about the user to memory."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_facts (fact, added_at) VALUES (?, ?)",
        (fact, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_user_facts() -> list:
    """Returns a list of dicts for all known facts about the user."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, fact, added_at FROM user_facts")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row["id"], "fact": row["fact"], "added_at": row["added_at"]} for row in rows]

def delete_user_fact(fact_id: int):
    """Deletes a fact by its ID."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_facts WHERE id = ?", (fact_id,))
    conn.commit()
    conn.close()


def get_or_create_user(telegram_id: str, display_name: str) -> int:
    """Gets an existing user by Telegram ID, or creates a new one. Returns the user_id."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM user_profiles WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    if row:
        conn.close()
        return row[0]
    
    cursor.execute(
        "INSERT INTO user_profiles (telegram_id, display_name, created_at) VALUES (?, ?, ?)",
        (telegram_id, display_name, datetime.now().isoformat())
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    print(f"[Memory] Created new user profile: {display_name} (ID: {user_id})")
    return user_id


# =============================================
# NEW: SEMANTIC MEMORY SYSTEM (Vector Embeddings)
# =============================================

def _generate_embedding(text: str) -> list:
    """
    Generates a vector embedding for the given text using Ollama's nomic-embed-text model.
    Returns a list of floats (the embedding vector).
    """
    try:
        import ollama
        result = ollama.embed(model=EMBED_MODEL, input=text)
        # ollama.embed returns {"embeddings": [[...floats...]]}
        embeddings = result.get("embeddings", [])
        if embeddings and len(embeddings) > 0:
            return embeddings[0]
        return []
    except Exception as e:
        print(f"[Memory] Embedding generation failed: {e}")
        return []


def _cosine_similarity(vec_a: list, vec_b: list) -> float:
    """Fallback python cosine similarity"""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    magnitude_a = math.sqrt(sum(a * a for a in vec_a))
    magnitude_b = math.sqrt(sum(b * b for b in vec_b))
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    return dot_product / (magnitude_a * magnitude_b)

# --- FAISS Index Management ---
_faiss_index = None
_faiss_id_map = {} # Maps FAISS index integer to SQLite row ID

def _init_faiss():
    global _faiss_index, _faiss_id_map
    if not FAISS_AVAILABLE:
        return
    
    # Nomic-embed-text uses 768 dimensions
    d = 768
    _faiss_index = faiss.IndexFlatIP(d) # Inner product (Cosine sim for normalized vectors)
    
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, embedding FROM semantic_memories")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return
        
    vectors = []
    _faiss_id_map = {}
    for i, row in enumerate(rows):
        try:
            emb = json.loads(row["embedding"])
            # Normalize vector for Cosine Similarity in Inner Product index
            emb = np.array(emb, dtype=np.float32)
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            vectors.append(emb)
            _faiss_id_map[i] = row["id"]
        except Exception:
            pass
            
    if vectors:
        vecs_np = np.array(vectors, dtype=np.float32)
        _faiss_index.add(vecs_np)
        print(f"[Memory] Initialized FAISS index with {len(vectors)} memories.")

# Initialize FAISS on load
_init_faiss()


def store_memory(content: str, category: str = "general") -> bool:
    """
    Stores a piece of information in semantic memory with its vector embedding.
    
    Categories: 'conversation', 'preference', 'fact', 'event', 'general'
    Returns True if successfully stored, False otherwise.
    """
    if not content or len(content.strip()) < 10:
        return False
    
    # Check for near-duplicate memories before storing
    existing = search_memories(content, top_k=1)
    if existing and existing[0]["similarity"] > 0.92:
        # Memory is too similar to an existing one, skip
        return False
    
    embedding = _generate_embedding(content)
    if not embedding:
        return False
    
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO semantic_memories (content, embedding, category, created_at) VALUES (?, ?, ?, ?)",
            (content.strip(), json.dumps(embedding), category, datetime.now().isoformat())
        )
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Update FAISS index
        global _faiss_index, _faiss_id_map
        if FAISS_AVAILABLE and _faiss_index is not None:
            emb = np.array(embedding, dtype=np.float32)
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            _faiss_index.add(np.array([emb]))
            _faiss_id_map[_faiss_index.ntotal - 1] = new_id
            
        print(f"[Memory] Stored: '{content[:60]}...' ({category})")
        return True
    except Exception as e:
        print(f"[Memory] Failed to store memory: {e}")
        return False


def search_memories(query: str, top_k: int = 3) -> list:
    """
    Searches semantic memories by cosine similarity to the query.
    
    Returns a list of dicts: [{"id", "content", "category", "created_at", "similarity"}]
    Sorted by similarity descending. Only returns matches with similarity > 0.5.
    """
    query_embedding = _generate_embedding(query)
    if not query_embedding:
        return []
    
    global _faiss_index, _faiss_id_map
    if FAISS_AVAILABLE and _faiss_index is not None and _faiss_index.ntotal > 0:
        # FAISS Accelerated Search
        emb = np.array(query_embedding, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
            
        # Search index
        k_search = min(top_k * 2, _faiss_index.ntotal)
        D, I = _faiss_index.search(np.array([emb]), k_search)
        
        # Fetch actual DB rows for the matching IDs
        match_ids = []
        sim_map = {}
        for i, (score, idx) in enumerate(zip(D[0], I[0])):
            if score > 0.5 and idx != -1 and idx in _faiss_id_map:
                db_id = _faiss_id_map[idx]
                match_ids.append(str(db_id))
                sim_map[db_id] = float(score)
                
        if not match_ids:
            return []
            
        id_list = ",".join(match_ids)
        conn = _get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, content, category, created_at FROM semantic_memories WHERE id IN ({id_list})")
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "content": row["content"],
                "category": row["category"],
                "created_at": row["created_at"],
                "similarity": round(sim_map.get(row["id"], 0), 4)
            })
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    # --- Fallback Pure-Python Search ---
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, content, embedding, category, created_at FROM semantic_memories")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return []
    
    scored = []
    for row in rows:
        try:
            stored_embedding = json.loads(row["embedding"])
            similarity = _cosine_similarity(query_embedding, stored_embedding)
            if similarity > 0.5:
                scored.append({
                    "id": row["id"],
                    "content": row["content"],
                    "category": row["category"],
                    "created_at": row["created_at"],
                    "similarity": round(similarity, 4)
                })
        except (json.JSONDecodeError, TypeError):
            continue
    
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]


def get_recent_memories(n: int = 5) -> list:
    """
    Returns the N most recent semantic memories (for temporal context).
    """
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, content, category, created_at FROM semantic_memories ORDER BY id DESC LIMIT ?", (n,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row["id"], "content": row["content"], "category": row["category"], "created_at": row["created_at"]} for row in rows]


def get_memory_count() -> int:
    """Returns the total number of stored semantic memories."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM semantic_memories")
    count = cursor.fetchone()[0]
    conn.close()
    return count


# =============================================
# PERSISTENT CONVERSATION HISTORY
# =============================================

def save_conversation_turn(role: str, content: str):
    """Persists a single conversation turn (user or assistant) to SQLite."""
    if not content or not content.strip():
        return
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversation_history (role, content, created_at) VALUES (?, ?, ?)",
        (role, content.strip(), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    # Auto-prune to prevent unbounded growth
    clear_old_history(keep_last=200)


def load_recent_history(n: int = 20) -> list:
    """
    Loads the last N conversation turns from the database.
    Returns a list of dicts: [{"role": "user", "content": "..."}]
    """
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM conversation_history ORDER BY id DESC LIMIT ?",
        (n,)
    )
    rows = cursor.fetchall()
    conn.close()
    # Reverse so oldest is first (chronological order)
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def clear_old_history(keep_last: int = 200):
    """Prunes old conversation history, keeping only the most recent N turns."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM conversation_history WHERE id NOT IN "
        "(SELECT id FROM conversation_history ORDER BY id DESC LIMIT ?)",
        (keep_last,)
    )
    conn.commit()
    conn.close()


# Initialize tables when the module is imported
init_db()
