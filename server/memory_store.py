import os
import json
import requests
import psycopg2
import psycopg2.extras
from datetime import datetime
from pgvector.psycopg2 import register_vector
from protocol.types import Memory, MemoryQuery, PrivacyLevel


def _detect_gpu() -> bool:
    """Return True if an NVIDIA GPU is available via nvidia-smi."""
    import subprocess
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False

_GPU_AVAILABLE: bool = _detect_gpu()


class MemoryStore:

    def __init__(self):
        self.db_url      = os.getenv("POSTGRES_URL")
        self.ollama_url  = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.embed_model = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")
        self.embed_dim   = self._detect_dim()
        self._init_db()
        device = "GPU (CUDA)" if _GPU_AVAILABLE else "CPU (no GPU found)"
        print(f"[MemoryStore] Ready | Model: {self.embed_model} | Dim: {self.embed_dim} | Device: {device}")

    # ─── EMBEDDING ────────────────────────────────────────────

    def embed(self, text: str) -> list[float]:
        resp = requests.post(
            f"{self.ollama_url}/api/embed",
            json={
                "model":   self.embed_model,
                "input":   text,
                "options": {"num_gpu": -1 if _GPU_AVAILABLE else 0},
            }
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        resp = requests.post(
            f"{self.ollama_url}/api/embed",
            json={
                "model":   self.embed_model,
                "input":   texts,
                "options": {"num_gpu": -1 if _GPU_AVAILABLE else 0},
            }
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]

    def _detect_dim(self) -> int:
        try:
            return len(self.embed("test"))
        except Exception:
            return 768  # fallback for nomic / bge-m3

    # ─── DATABASE ─────────────────────────────────────────────

    def _get_conn(self):
        conn = psycopg2.connect(self.db_url)
        register_vector(conn)
        return conn

    def _init_db(self):
        # Use raw connection first to create extension before registering vector
        conn = psycopg2.connect(self.db_url)
        cur  = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        conn.close()

        conn = self._get_conn()
        cur  = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS memories (
                id            TEXT PRIMARY KEY,
                user_id       TEXT NOT NULL DEFAULT 'default',
                content       TEXT NOT NULL,
                embedding     vector({self.embed_dim}),
                type          TEXT DEFAULT 'semantic',
                entity        TEXT DEFAULT 'user',
                confidence    FLOAT DEFAULT 0.8,
                privacy       TEXT DEFAULT 'global',
                app_id        TEXT DEFAULT 'unknown',
                tags          JSONB DEFAULT '[]',
                created_at    TIMESTAMPTZ DEFAULT NOW(),
                last_accessed TIMESTAMPTZ DEFAULT NOW(),
                access_count  INTEGER DEFAULT 0,
                expires_at    TIMESTAMPTZ,
                metadata      JSONB DEFAULT '{{}}'
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_embedding
            ON memories USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON memories(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_app_id  ON memories(app_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_privacy ON memories(privacy)")

        # ── Sessions table ──────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id    TEXT NOT NULL DEFAULT 'default',
                app_id     TEXT NOT NULL DEFAULT 'unknown',
                messages   JSONB NOT NULL DEFAULT '[]',
                title      TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_session_user  ON sessions(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_session_app   ON sessions(app_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_session_sid   ON sessions(session_id)")
        conn.commit()
        conn.close()

    # ─── STORE ────────────────────────────────────────────────

    def store(self, memory: Memory, user_id: str = "default") -> Memory:
        existing = self._find_duplicate(memory.content, user_id)
        if existing:
            self._boost_confidence(existing["id"])
            memory.id = existing["id"]
            return memory

        embedding = self.embed(memory.content)

        conn = self._get_conn()
        conn.cursor().execute("""
            INSERT INTO memories
                (id, user_id, content, embedding, type, entity,
                 confidence, privacy, app_id, tags, metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
        """, (
            memory.id, user_id, memory.content, embedding,
            memory.type.value, memory.entity, memory.confidence,
            memory.privacy.value, memory.app_id,
            json.dumps(memory.tags), json.dumps(memory.metadata)
        ))
        conn.commit()
        conn.close()
        print(f"[Store] ✓ '{memory.content[:60]}'")
        return memory

    def store_batch(self, memories: list[Memory], user_id: str = "default") -> list[Memory]:
        if not memories:
            return []
        embeddings = self.embed_batch([m.content for m in memories])
        conn = self._get_conn()
        cur  = conn.cursor()
        saved = []
        for memory, embedding in zip(memories, embeddings):
            existing = self._find_duplicate(memory.content, user_id)
            if existing:
                self._boost_confidence(existing["id"])
                memory.id = existing["id"]
            else:
                cur.execute("""
                    INSERT INTO memories
                        (id, user_id, content, embedding, type, entity,
                         confidence, privacy, app_id, tags)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    memory.id, user_id, memory.content, embedding,
                    memory.type.value, memory.entity, memory.confidence,
                    memory.privacy.value, memory.app_id, json.dumps(memory.tags)
                ))
            saved.append(memory)
        conn.commit()
        conn.close()
        print(f"[Store] Batch saved {len(saved)} memories")
        return saved

    # ─── RETRIEVE ─────────────────────────────────────────────

    def retrieve(self, query: MemoryQuery) -> list[dict]:
        query_embedding = self.embed(query.query)
        conn = self._get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT
                id, content, type, entity,
                confidence, app_id, tags, created_at,
                1 - (embedding <=> %s::vector) AS similarity
            FROM memories
            WHERE
                user_id = %s
                AND (
                    privacy = 'global'
                    OR (privacy = 'app_shared' AND app_id = %s)
                    OR (privacy = 'private'    AND app_id = %s)
                )
                AND confidence >= %s
                AND (expires_at IS NULL OR expires_at > NOW())
                AND 1 - (embedding <=> %s::vector) > 0.55
            ORDER BY similarity DESC
            LIMIT %s
        """, (
            query_embedding, query.user_id,
            query.app_id, query.app_id,
            query.min_confidence,
            query_embedding, query.limit
        ))

        rows = cur.fetchall()
        if rows:
            cur.execute("""
                UPDATE memories
                SET access_count  = access_count + 1,
                    last_accessed = NOW()
                WHERE id = ANY(%s)
            """, ([r["id"] for r in rows],))
            conn.commit()
        conn.close()

        return [
            {
                "id":         r["id"],
                "content":    r["content"],
                "type":       r["type"],
                "confidence": float(r["confidence"]),
                "relevance":  round(float(r["similarity"]), 3),
                "tags":       r["tags"] or [],
                "app_id":     r["app_id"],
            }
            for r in rows
        ]

    # ─── HELPERS ──────────────────────────────────────────────

    def _find_duplicate(self, content: str, user_id: str, threshold: float = 0.88) -> dict | None:
        conn = self._get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # 1. Exact match first (fast, no embedding needed)
        cur.execute(
            "SELECT id, content FROM memories WHERE user_id = %s AND content = %s LIMIT 1",
            (user_id, content)
        )
        row = cur.fetchone()
        if row:
            conn.close()
            return dict(row)
        conn.close()
        # 2. Semantic similarity check
        embedding = self.embed(content)
        conn = self._get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, content, 1 - (embedding <=> %s::vector) AS similarity
            FROM memories
            WHERE user_id = %s
              AND 1 - (embedding <=> %s::vector) > %s
            ORDER BY similarity DESC LIMIT 1
        """, (embedding, user_id, embedding, threshold))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def _boost_confidence(self, memory_id: str):
        conn = self._get_conn()
        conn.cursor().execute("""
            UPDATE memories
            SET confidence    = LEAST(1.0, confidence + 0.05),
                access_count  = access_count + 1,
                last_accessed = NOW()
            WHERE id = %s
        """, (memory_id,))
        conn.commit()
        conn.close()

    def delete(self, memory_id: str) -> bool:
        conn = self._get_conn()
        cur  = conn.cursor()
        cur.execute("DELETE FROM memories WHERE id = %s", (memory_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def get_all(self, user_id: str = "default", limit: int = 100) -> list[dict]:
        conn = self._get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, content, type, confidence, tags, app_id, created_at, access_count
            FROM memories
            WHERE user_id = %s
            ORDER BY last_accessed DESC LIMIT %s
        """, (user_id, limit))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ─── SESSIONS ─────────────────────────────────────────────

    def upsert_session(
        self,
        session_id: str,
        messages:   list[dict],
        user_id:    str = "default",
        app_id:     str = "unknown",
        title:      str = "",
    ) -> dict:
        """Insert or update a conversation session."""
        import uuid
        conn = self._get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Check if session exists
        cur.execute("SELECT id, messages FROM sessions WHERE session_id = %s AND user_id = %s",
                    (session_id, user_id))
        existing = cur.fetchone()

        if existing:
            # Merge new messages (avoid duplicates by content)
            old_msgs = existing["messages"] or []
            existing_texts = {(m["role"], m["content"]) for m in old_msgs}
            new_msgs = [m for m in messages if (m["role"], m["content"]) not in existing_texts]
            merged = old_msgs + new_msgs
            cur.execute("""
                UPDATE sessions
                SET messages = %s, updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(merged), existing["id"]))
            record_id = existing["id"]
        else:
            record_id = f"sess_{uuid.uuid4().hex[:12]}"
            # Auto-generate title from first user message
            if not title:
                for m in messages:
                    if m["role"] == "user":
                        title = m["content"][:60]
                        break
            cur.execute("""
                INSERT INTO sessions (id, session_id, user_id, app_id, messages, title)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (record_id, session_id, user_id, app_id, json.dumps(messages), title))

        conn.commit()
        conn.close()
        return {"id": record_id, "session_id": session_id}

    def get_sessions(self, user_id: str = "default", app_id: str = None, limit: int = 50) -> list[dict]:
        conn = self._get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if app_id:
            cur.execute("""
                SELECT id, session_id, app_id, title,
                       jsonb_array_length(messages) AS message_count,
                       created_at, updated_at
                FROM sessions
                WHERE user_id = %s AND app_id = %s
                ORDER BY updated_at DESC LIMIT %s
            """, (user_id, app_id, limit))
        else:
            cur.execute("""
                SELECT id, session_id, app_id, title,
                       jsonb_array_length(messages) AS message_count,
                       created_at, updated_at
                FROM sessions
                WHERE user_id = %s
                ORDER BY updated_at DESC LIMIT %s
            """, (user_id, limit))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str, user_id: str = "default") -> dict | None:
        conn = self._get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, session_id, app_id, title, messages, created_at, updated_at
            FROM sessions WHERE session_id = %s AND user_id = %s
        """, (session_id, user_id))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def stats(self) -> dict:
        conn = self._get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM memories")
        total = cur.fetchone()[0]
        cur.execute("SELECT type, COUNT(*) FROM memories GROUP BY type")
        by_type = dict(cur.fetchall())
        cur.execute("SELECT app_id, COUNT(*) FROM memories GROUP BY app_id")
        by_app = dict(cur.fetchall())
        conn.close()
        return {"total_memories": total, "by_type": by_type, "by_app": by_app}
