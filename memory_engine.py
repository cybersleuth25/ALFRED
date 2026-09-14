import sqlite3
import os
import json
import math
import numpy as np
import threading
from datetime import datetime
from logger import logger
from dotenv import load_dotenv

load_dotenv()

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

DB_PATH = os.path.join(os.path.dirname(__file__), "alfred_memory.db")

# --- Embedding Configuration ---
# Uses sentence-transformers (local, ~80MB, no GPU needed)
_st_model = None
_st_model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBED_DIM = 384  # Dimension for all-MiniLM-L6-v2

def _get_st_model():
    """Lazy-load the sentence-transformers model on first use."""
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"[Memory] Loading embedding model '{_st_model_name}' (first use)...")
            _st_model = SentenceTransformer(_st_model_name)
            logger.info(f"[Memory] Embedding model loaded. Dimension: {EMBED_DIM}")
        except ImportError:
            logger.error("[Memory] sentence-transformers not installed. Run: pip install sentence-transformers")
        except Exception as e:
            logger.error(f"[Memory] Failed to load embedding model: {e}")
    return _st_model

_db_lock = threading.RLock()

def with_db_lock(func):
    """Decorator to serialize SQLite database access."""
    import functools
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with _db_lock:
            return func(*args, **kwargs)
    return wrapper

def _get_connection():
    """Returns a SQLite connection."""
    return sqlite3.connect(DB_PATH, timeout=30.0)

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
    
    # --- Focus Mode: Study Sessions ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            duration_minutes INTEGER DEFAULT 0,
            distractions INTEGER DEFAULT 0,
            focus_score INTEGER DEFAULT 100,
            pomodoro_cycles INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            briefing TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_distractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            distraction_type TEXT NOT NULL,
            detail TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES study_sessions(id)
        )
    """)
    
    # --- Contextual Awareness: Context Snapshots ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS context_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            activity TEXT NOT NULL,
            active_window TEXT,
            screen_hash TEXT,
            presence TEXT DEFAULT 'present',
            dwell_seconds INTEGER DEFAULT 0
        )
    """)
    
    # --- Workflow Macros / Routines ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            trigger_phrases TEXT NOT NULL,
            description TEXT,
            steps TEXT NOT NULL,
            is_builtin INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            last_run TEXT
        )
    """)

    # --- Emotional Intelligence / Mood Tracking ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_moods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            emotion TEXT NOT NULL,
            confidence REAL DEFAULT 1.0,
            context TEXT
        )
    """)

    # --- Local Knowledge Graph / Second Brain ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            entity_type TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            relation TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
            FOREIGN KEY(target_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
            UNIQUE(source_id, target_id, relation)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            incident_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            details TEXT NOT NULL,
            snapshot_path TEXT,
            resolved INTEGER DEFAULT 0
        )
    """)
    
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
    logger.info(f"[Memory] Created new user profile: {display_name} (ID: {user_id})")
    return user_id


# =============================================
# NEW: SEMANTIC MEMORY SYSTEM (Vector Embeddings)
# =============================================

def _generate_embedding(text: str) -> list:
    """
    Generates a vector embedding for the given text using sentence-transformers (local, no API needed).
    Returns a list of floats (the embedding vector).
    """
    try:
        model = _get_st_model()
        if model is None:
            return []
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"[Memory] Embedding generation failed: {e}")
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
    
    # all-MiniLM-L6-v2 uses 384 dimensions
    d = EMBED_DIM
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
    for row in rows:
        try:
            emb = json.loads(row["embedding"])
            if len(emb) != d:
                logger.warning(f"[Memory] Skipping memory ID {row['id']} due to dimension mismatch ({len(emb)} != {d})")
                continue
            # Normalize vector for Cosine Similarity in Inner Product index
            emb = np.array(emb, dtype=np.float32)
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            vectors.append(emb)
            _faiss_id_map[len(vectors) - 1] = row["id"]
        except Exception:
            pass
            
    if vectors:
        vecs_np = np.array(vectors, dtype=np.float32)
        _faiss_index.add(vecs_np)
        logger.info(f"[Memory] Initialized FAISS index with {len(vectors)} memories.")

# FAISS initialization moved to end of file after init_db()


def store_memory(content: str, category: str = "general") -> bool:
    """
    Stores a piece of information in semantic memory with its vector embedding.
    
    Categories: 'conversation', 'preference', 'fact', 'event', 'general'
    Returns True if successfully stored, False otherwise.
    """
    if not content or len(content.strip()) < 10:
        return False
    
    # Generate embedding once, reuse for both duplicate check and storage
    embedding = _generate_embedding(content)
    if not embedding:
        return False
    
    # Check for near-duplicate memories before storing (reuse embedding)
    existing = search_memories(content, top_k=1, query_embedding=embedding)
    if existing and existing[0]["similarity"] > 0.92:
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
            
        logger.info(f"[Memory] Stored: '{content[:60]}...' ({category})")
        return True
    except Exception as e:
        logger.error(f"[Memory] Failed to store memory: {e}")
        return False


def search_memories(query: str, top_k: int = 3, query_embedding: list = None) -> list:
    """
    Searches semantic memories by cosine similarity to the query.
    
    Returns a list of dicts: [{"id", "content", "category", "created_at", "similarity"}]
    Sorted by similarity descending. Only returns matches with similarity > 0.5.
    """
    if query_embedding is None:
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
        placeholders = ",".join("?" for _ in match_ids)
        cursor.execute(f"SELECT id, content, category, created_at FROM semantic_memories WHERE id IN ({placeholders})", [int(mid) for mid in match_ids])
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

_save_counter = 0

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
    # Auto-prune every 50 saves to prevent unbounded growth without full-table scan overhead
    global _save_counter
    _save_counter += 1
    if _save_counter >= 50:
        _save_counter = 0
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


# =============================================
# FOCUS MODE: STUDY SESSION TRACKING
# =============================================

def create_study_session() -> int:
    """Creates a new study session and returns its ID."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO study_sessions (started_at, status) VALUES (?, 'active')",
        (datetime.now().isoformat(),)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"[Memory] Created study session #{session_id}")
    return session_id


def end_study_session(session_id: int, briefing: str = "", pomodoro_cycles: int = 0):
    """Marks a study session as completed and calculates the focus score."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    # Get session start time and distraction count
    cursor.execute("SELECT started_at, distractions FROM study_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
    
    started_at = row[0]
    distractions = row[1] or 0
    
    # Calculate duration
    try:
        start_dt = datetime.fromisoformat(started_at)
        duration_minutes = max(1, int((datetime.now() - start_dt).total_seconds() / 60))
    except Exception:
        duration_minutes = 0
    
    # Focus score: starts at 100, loses points per distraction relative to session length
    # Short sessions are penalized more per distraction
    penalty_per_distraction = max(5, 30 - duration_minutes)  # Longer sessions = smaller penalty
    focus_score = max(0, 100 - (distractions * penalty_per_distraction))
    
    cursor.execute("""
        UPDATE study_sessions 
        SET ended_at = ?, duration_minutes = ?, focus_score = ?, 
            pomodoro_cycles = ?, status = 'completed', briefing = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), duration_minutes, focus_score, 
          pomodoro_cycles, briefing, session_id))
    conn.commit()
    conn.close()
    logger.info(f"[Memory] Ended study session #{session_id}: {duration_minutes}min, score={focus_score}, distractions={distractions}")


def log_study_distraction(session_id: int, distraction_type: str, detail: str = ""):
    """Logs a distraction event and increments the session counter."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO study_distractions (session_id, distraction_type, detail, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, distraction_type, detail, datetime.now().isoformat())
    )
    cursor.execute(
        "UPDATE study_sessions SET distractions = distractions + 1 WHERE id = ?",
        (session_id,)
    )
    conn.commit()
    conn.close()


def get_active_study_session():
    """Returns the currently active study session, or None. Used for crash recovery."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM study_sessions WHERE status = 'active' ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def close_orphaned_sessions():
    """Marks any lingering 'active' sessions as 'crashed'. Called on startup."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE study_sessions 
        SET status = 'crashed', ended_at = ?, focus_score = 0
        WHERE status = 'active'
    """, (datetime.now().isoformat(),))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    if affected > 0:
        logger.info(f"[Memory] Closed {affected} orphaned study session(s) from a previous crash.")


def get_study_history(last_n: int = 10) -> list:
    """Returns the last N completed study sessions."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, started_at, ended_at, duration_minutes, distractions, 
               focus_score, pomodoro_cycles, status, briefing
        FROM study_sessions 
        WHERE status IN ('completed', 'crashed')
        ORDER BY id DESC LIMIT ?
    """, (last_n,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_study_stats() -> dict:
    """Returns aggregate study statistics."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_sessions,
            COALESCE(SUM(duration_minutes), 0) as total_minutes,
            COALESCE(AVG(focus_score), 0) as avg_focus_score,
            COALESCE(SUM(distractions), 0) as total_distractions,
            COALESCE(SUM(pomodoro_cycles), 0) as total_pomodoros,
            COALESCE(MAX(duration_minutes), 0) as longest_session
        FROM study_sessions WHERE status = 'completed'
    """)
    row = cursor.fetchone()
    conn.close()
    
    if row:
        total_hours = round(row[1] / 60, 1)
        return {
            "total_sessions": row[0],
            "total_hours": total_hours,
            "avg_focus_score": round(row[2]),
            "total_distractions": row[3],
            "total_pomodoros": row[4],
            "longest_session_min": row[5]
        }
    return {
        "total_sessions": 0, "total_hours": 0, "avg_focus_score": 0,
        "total_distractions": 0, "total_pomodoros": 0, "longest_session_min": 0
    }


def get_session_distractions(session_id: int) -> list:
    """Returns all distraction events for a given session."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, distraction_type, detail, timestamp FROM study_distractions WHERE session_id = ? ORDER BY id",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_daily_study_minutes() -> int:
    """Returns total minutes studied today (completed sessions only)."""
    conn = _get_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT COALESCE(SUM(duration_minutes), 0)
        FROM study_sessions 
        WHERE status = 'completed' AND started_at LIKE ?
    """, (f"{today}%",))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0


def get_study_streak() -> int:
    """Returns the number of consecutive days with at least one completed session."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT DATE(started_at) as study_date
        FROM study_sessions 
        WHERE status = 'completed'
        ORDER BY study_date DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return 0
    
    from datetime import timedelta
    streak = 0
    expected_date = datetime.now().date()
    
    for row in rows:
        try:
            study_date = datetime.strptime(row[0], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        
        if study_date == expected_date:
            streak += 1
            expected_date -= timedelta(days=1)
        elif study_date == expected_date - timedelta(days=1):
            # Allow for "today hasn't been studied yet but yesterday was"
            streak += 1
            expected_date = study_date - timedelta(days=1)
        else:
            break
    
    return streak


def get_distraction_breakdown(session_id: int) -> dict:
    """Returns a categorized distraction breakdown for focus score explanation."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT distraction_type, COUNT(*) as count
        FROM study_distractions 
        WHERE session_id = ?
        GROUP BY distraction_type
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def get_hourly_focus_data() -> list:
    """
    Returns a 24-element list representing today's hourly focus data.
    Each element: {"hour": 0-23, "distractions": int, "active": bool}
    Used to render the focus heatmap in FocusPanel.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Get today's sessions to determine which hours had active study
    cursor.execute("""
        SELECT started_at, ended_at FROM study_sessions 
        WHERE started_at LIKE ? AND status IN ('completed', 'active')
    """, (f"{today}%",))
    sessions = cursor.fetchall()
    
    # Get today's distractions grouped by hour
    cursor.execute("""
        SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, COUNT(*) as count
        FROM study_distractions 
        WHERE timestamp LIKE ?
        GROUP BY hour
    """, (f"{today}%",))
    distraction_rows = cursor.fetchall()
    conn.close()
    
    distractions_by_hour = {row[0]: row[1] for row in distraction_rows}
    
    # Determine which hours had active study sessions
    active_hours = set()
    for session in sessions:
        try:
            start = datetime.fromisoformat(session[0])
            end = datetime.fromisoformat(session[1]) if session[1] else datetime.now()
            for h in range(start.hour, min(end.hour + 1, 24)):
                active_hours.add(h)
        except (ValueError, TypeError):
            continue
    
    result = []
    for h in range(24):
        result.append({
            "hour": h,
            "distractions": distractions_by_hour.get(h, 0),
            "active": h in active_hours
        })
    return result


# =============================================
# MEMORY CLEARING (Full Wipe Support)
# =============================================

# =============================================
# CONTEXTUAL AWARENESS FUNCTIONS
# =============================================

def store_context_snapshot(activity: str, active_window: str = "",
                          screen_hash: str = "", presence: str = "present",
                          dwell_seconds: int = 0):
    """Stores a context snapshot for activity tracking."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO context_snapshots (timestamp, activity, active_window, screen_hash, presence, dwell_seconds) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), activity, active_window[:200] if active_window else "",
         screen_hash or "", presence, dwell_seconds)
    )
    conn.commit()
    conn.close()


def get_recent_context(minutes: int = 60) -> list:
    """Returns context snapshots from the last N minutes."""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT timestamp, activity, active_window, presence, dwell_seconds FROM context_snapshots WHERE timestamp > ? ORDER BY timestamp DESC",
        (cutoff,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{
        "timestamp": row["timestamp"],
        "activity": row["activity"],
        "active_window": row["active_window"],
        "presence": row["presence"],
        "dwell_seconds": row["dwell_seconds"],
    } for row in rows]


def get_current_activity_summary() -> str:
    """Returns a brief text summary of recent activity (last 30 min)."""
    snapshots = get_recent_context(30)
    if not snapshots:
        return "No recent activity data."
    
    # Count time per activity
    activity_counts = {}
    for s in snapshots:
        act = s["activity"]
        activity_counts[act] = activity_counts.get(act, 0) + 1
    
    # Most common activity
    top_activity = max(activity_counts, key=activity_counts.get)
    total = sum(activity_counts.values())
    pct = int(activity_counts[top_activity] / total * 100)
    
    return f"Primarily {top_activity} ({pct}% of last 30 min). {len(snapshots)} snapshots recorded."


def cleanup_old_context(days: int = 7):
    """Deletes context snapshots older than N days to prevent DB bloat."""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM context_snapshots WHERE timestamp < ?", (cutoff,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    if deleted > 0:
        logger.info(f"[Memory] Cleaned up {deleted} old context snapshots (>{days} days).")


# =============================================
# WORKFLOW ROUTINES PERSISTENCE
# =============================================

def save_routine(name: str, display_name: str, trigger_phrases: list,
                 description: str, steps: list, is_builtin: bool = False) -> int:
    """Creates or updates a routine in the database."""
    import json
    triggers_json = json.dumps(trigger_phrases) if isinstance(trigger_phrases, list) else trigger_phrases
    steps_json = json.dumps(steps) if isinstance(steps, list) else steps
    created_at = datetime.now().isoformat()

    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO routines (name, display_name, trigger_phrases, description, steps, is_builtin, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            display_name=excluded.display_name,
            trigger_phrases=excluded.trigger_phrases,
            description=excluded.description,
            steps=excluded.steps,
            is_builtin=excluded.is_builtin
    """, (name.lower().strip(), display_name, triggers_json, description, steps_json, 1 if is_builtin else 0, created_at))
    routine_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return routine_id


def get_all_routines() -> list:
    """Returns all configured routines."""
    import json
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM routines ORDER BY is_builtin DESC, name ASC")
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        try:
            triggers = json.loads(r["trigger_phrases"])
        except Exception:
            triggers = []
        try:
            steps = json.loads(r["steps"])
        except Exception:
            steps = []
        result.append({
            "id": r["id"],
            "name": r["name"],
            "display_name": r["display_name"],
            "trigger_phrases": triggers,
            "description": r["description"],
            "steps": steps,
            "is_builtin": bool(r["is_builtin"]),
            "created_at": r["created_at"],
            "last_run": r["last_run"],
        })
    return result


def get_routine(name_or_id) -> dict:
    """Fetches a single routine by integer ID or string name."""
    import json
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
        cursor.execute("SELECT * FROM routines WHERE id = ?", (int(name_or_id),))
    else:
        cursor.execute("SELECT * FROM routines WHERE name = ?", (str(name_or_id).lower().strip(),))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None
    try:
        triggers = json.loads(row["trigger_phrases"])
    except Exception:
        triggers = []
    try:
        steps = json.loads(row["steps"])
    except Exception:
        steps = []
    return {
        "id": row["id"],
        "name": row["name"],
        "display_name": row["display_name"],
        "trigger_phrases": triggers,
        "description": row["description"],
        "steps": steps,
        "is_builtin": bool(row["is_builtin"]),
        "created_at": row["created_at"],
        "last_run": row["last_run"],
    }


def delete_routine(name_or_id) -> bool:
    """Deletes a routine (built-in routines cannot be deleted)."""
    conn = _get_connection()
    cursor = conn.cursor()
    if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
        cursor.execute("DELETE FROM routines WHERE id = ? AND is_builtin = 0", (int(name_or_id),))
    else:
        cursor.execute("DELETE FROM routines WHERE name = ? AND is_builtin = 0", (str(name_or_id).lower().strip(),))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def update_routine_last_run(name: str):
    """Updates the last_run timestamp for a routine."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE routines SET last_run = ? WHERE name = ?", (datetime.now().isoformat(), name.lower().strip()))
    conn.commit()
    conn.close()


# =============================================
# MOOD TRACKING PERSISTENCE
# =============================================

def log_user_mood(emotion: str, confidence: float = 1.0, context: str = ""):
    """Logs an emotion snapshot to the user_moods table."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_moods (timestamp, emotion, confidence, context) VALUES (?, ?, ?, ?)",
        (datetime.now().isoformat(), emotion.lower().strip(), float(confidence), context or "")
    )
    conn.commit()
    conn.close()


def get_recent_moods(hours: int = 24) -> list:
    """Retrieves user mood snapshots from the past N hours."""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, timestamp, emotion, confidence, context FROM user_moods WHERE timestamp > ? ORDER BY timestamp ASC",
        (cutoff,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{
        "id": r["id"],
        "timestamp": r["timestamp"],
        "emotion": r["emotion"],
        "confidence": r["confidence"],
        "context": r["context"],
    } for r in rows]


def get_dominant_mood_recent(minutes: int = 30) -> str:
    """Returns the most frequent mood in the last N minutes."""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT emotion, COUNT(*) as cnt FROM user_moods WHERE timestamp > ? GROUP BY emotion ORDER BY cnt DESC LIMIT 1",
        (cutoff,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "neutral"


# =============================================
# KNOWLEDGE GRAPH PERSISTENCE
# =============================================

def add_knowledge_node(name: str, entity_type: str = "concept", description: str = "") -> int:
    """Adds or updates a node in the knowledge graph. Returns node id."""
    now = datetime.now().isoformat()
    clean_name = name.strip()
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO knowledge_nodes (name, entity_type, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            entity_type=excluded.entity_type,
            description=CASE WHEN excluded.description != '' THEN excluded.description ELSE knowledge_nodes.description END,
            updated_at=excluded.updated_at
    """, (clean_name, entity_type.lower().strip(), description or "", now, now))
    
    cursor.execute("SELECT id FROM knowledge_nodes WHERE name = ?", (clean_name,))
    row = cursor.fetchone()
    node_id = row[0] if row else cursor.lastrowid
    conn.commit()
    conn.close()
    return node_id


def add_knowledge_edge(source_name: str, target_name: str, relation: str, weight: float = 1.0) -> bool:
    """Creates a directed relationship between two named entities."""
    source_id = add_knowledge_node(source_name)
    target_id = add_knowledge_node(target_name)
    if source_id == target_id:
        return False
    now = datetime.now().isoformat()
    clean_rel = relation.upper().strip().replace(" ", "_")

    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO knowledge_edges (source_id, target_id, relation, weight, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_id, target_id, relation) DO UPDATE SET
                weight=excluded.weight
        """, (source_id, target_id, clean_rel, float(weight), now))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return False


def get_all_knowledge_nodes() -> list:
    """Returns all nodes in the knowledge graph."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM knowledge_nodes ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_knowledge_edges() -> list:
    """Returns all edges in the knowledge graph with node names resolved."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, e.source_id, e.target_id, e.relation, e.weight, e.created_at,
               s.name as source_name, s.entity_type as source_type,
               t.name as target_name, t.entity_type as target_type
        FROM knowledge_edges e
        JOIN knowledge_nodes s ON e.source_id = s.id
        JOIN knowledge_nodes t ON e.target_id = t.id
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_node_subgraph(name: str, depth: int = 2) -> dict:
    """
    Returns 1st and 2nd degree connected nodes and edges for a given entity name.
    Useful for multi-hop graph retrieval and reasoning.
    """
    clean_name = name.strip()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM knowledge_nodes WHERE name LIKE ?", (clean_name,))
    root = cursor.fetchone()
    if not root:
        conn.close()
        return {"nodes": [], "edges": []}

    visited_node_ids = {root["id"]}
    collected_edges = []

    # BFS up to depth
    current_level = {root["id"]}
    for _ in range(depth):
        if not current_level:
            break
        placeholders = ",".join("?" * len(current_level))
        cursor.execute(f"""
            SELECT e.id, e.source_id, e.target_id, e.relation, e.weight,
                   s.name as source_name, t.name as target_name
            FROM knowledge_edges e
            JOIN knowledge_nodes s ON e.source_id = s.id
            JOIN knowledge_nodes t ON e.target_id = t.id
            WHERE e.source_id IN ({placeholders}) OR e.target_id IN ({placeholders})
        """, list(current_level) + list(current_level))
        edges = cursor.fetchall()
        
        next_level = set()
        for e in edges:
            collected_edges.append(dict(e))
            for nid in (e["source_id"], e["target_id"]):
                if nid not in visited_node_ids:
                    visited_node_ids.add(nid)
                    next_level.add(nid)
        current_level = next_level

    # Fetch all collected node details
    if visited_node_ids:
        placeholders = ",".join("?" * len(visited_node_ids))
        cursor.execute(f"SELECT * FROM knowledge_nodes WHERE id IN ({placeholders})", list(visited_node_ids))
        nodes = cursor.fetchall()
    else:
        nodes = []

    conn.close()
    return {
        "nodes": [dict(n) for n in nodes],
        "edges": collected_edges
    }




def clear_all_semantic_memories():
    """Wipes all semantic memories from the database and rebuilds the FAISS index."""
    global _faiss_index, _faiss_id_map
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM semantic_memories")
    conn.commit()
    conn.close()
    # Rebuild FAISS index (empty)
    if FAISS_AVAILABLE:
        _faiss_index = faiss.IndexFlatIP(EMBED_DIM)
        _faiss_id_map = {}
    logger.info("[Memory] All semantic memories cleared and FAISS index rebuilt.")


def clear_all_conversation_history():
    """Wipes all conversation history from the database."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversation_history")
    conn.commit()
    conn.close()
    logger.info("[Memory] All conversation history cleared.")


def clear_everything():
    """
    Nuclear option: wipes ALL memory data — user facts, semantic memories,
    conversation history — and rebuilds FAISS. Used when the user says
    'forget everything' or 'clear all memories'.
    """
    global _faiss_index, _faiss_id_map
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_facts")
    cursor.execute("DELETE FROM semantic_memories")
    cursor.execute("DELETE FROM conversation_history")
    conn.commit()
    conn.close()
    # Rebuild FAISS index (empty)
    if FAISS_AVAILABLE:
        _faiss_index = faiss.IndexFlatIP(EMBED_DIM)
        _faiss_id_map = {}
    logger.info("[Memory] ALL memory data wiped (facts, semantic, conversation) and FAISS rebuilt.")


# =============================================
# FEATURE 5: SECURITY INCIDENTS HELPERS
# =============================================

def log_security_incident(incident_type: str, severity: str, details: str, snapshot_path: str = None) -> int:
    """Logs a security tripwire incident to SQLite."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO security_incidents (timestamp, incident_type, severity, details, snapshot_path, resolved) VALUES (?, ?, ?, ?, ?, 0)",
        (datetime.now().isoformat(), incident_type, severity, details, snapshot_path)
    )
    inc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return inc_id

def get_security_incidents(limit: int = 50, unresolved_only: bool = False) -> list:
    """Returns security incidents sorted newest first."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if unresolved_only:
        cursor.execute("SELECT * FROM security_incidents WHERE resolved = 0 ORDER BY id DESC LIMIT ?", (limit,))
    else:
        cursor.execute("SELECT * FROM security_incidents ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def resolve_security_incident(incident_id: int):
    """Marks a security incident as resolved."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE security_incidents SET resolved = 1 WHERE id = ?", (incident_id,))
    conn.commit()
    conn.close()


# Decorate all database-access functions dynamically
for name in list(globals().keys()):
    if name.startswith('_') or name in ('with_db_lock', 'FAISS_AVAILABLE'):
        continue
    obj = globals()[name]
    if callable(obj) and not isinstance(obj, type):
        globals()[name] = with_db_lock(obj)

# Initialize tables when the module is imported
init_db()

# Initialize FAISS on load
_init_faiss()

