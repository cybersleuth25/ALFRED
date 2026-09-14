import os
import sys
import tempfile
import sqlite3
import math
import pytest
from unittest.mock import MagicMock

# Ensure the root directory of the project is on the Python path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 1. Create a persistent temporary database file path for the test session
test_db_fd, test_db_path = tempfile.mkstemp(suffix=".db", prefix="alfred_test_")
os.close(test_db_fd)

# 2. Redirect sqlite3.connect transparently to the test database
_original_connect = sqlite3.connect

def mock_connect(database, *args, **kwargs):
    # If it is connecting to the production database or any test database, redirect to test_db_path
    if isinstance(database, str) and ("alfred_memory.db" in database or "alfred_test" in database):
        return _original_connect(test_db_path, *args, **kwargs)
    return _original_connect(database, *args, **kwargs)

sqlite3.connect = mock_connect

# Now we can safely import shared and memory_engine, knowing their on-load
# actions (like init_db() and _init_faiss()) will run on the test database.
import shared
import memory_engine

# Explicitly patch DB_PATH to point to our test database path
memory_engine.DB_PATH = test_db_path

def pytest_sessionfinish(session, exitstatus):
    """Clean up the test database file after the entire session completes."""
    try:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
    except Exception:
        pass

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """
    Fixture that runs before each test. It clears all tables in the temporary database
    and sets up deterministic mocks for vector embeddings.
    """
    # 1. Truncate all tables in the test database to start fresh
    conn = _original_connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall() if row[0] != 'sqlite_sequence']
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()

    # 2. Provide a deterministic dummy embedding generator (768 dimensions)
    # based on the content of the string to test vector similarities.
    def mock_generate_embedding(text):
        if not text:
            return []
        # Return a normalized sine wave based on length and characters
        seed = len(text) + (ord(text[0]) if len(text) > 0 else 0)
        vec = [math.sin(seed + i) for i in range(768)]
        # Normalize the vector to unit length
        norm = math.sqrt(sum(x*x for x in vec))
        if norm > 0:
            vec = [x/norm for x in vec]
        return vec

    monkeypatch.setattr(memory_engine, "_generate_embedding", mock_generate_embedding)

    # 3. Mock the local client embedding API in the shared module
    mock_client = MagicMock()
    def mock_embed(model, input):
        if isinstance(input, str):
            return {"embeddings": [mock_generate_embedding(input)]}
        elif isinstance(input, list):
            return {"embeddings": [mock_generate_embedding(t) for t in input]}
        return {"embeddings": []}
    mock_client.embed = mock_embed

    def mock_chat(*args, **kwargs):
        is_stream = kwargs.get("stream", False)
        if is_stream:
            return [
                {"message": {"content": "[MOOD: calm] Hello, I "}},
                {"message": {"content": "am a mock "}},
                {"message": {"content": "agent."}}
            ]
        else:
            return {
                "message": {
                    "content": '{"thought": "Mock thought", "response": "Hello, I am a mock agent.", "tools_to_call": []}'
                }
            }
    mock_client.chat = MagicMock(side_effect=mock_chat)
    monkeypatch.setattr(shared, "local_client", mock_client)

    # 4. Re-initialize tables and the FAISS index for the fresh/empty database
    memory_engine.init_db()
    memory_engine._init_faiss()
