"""Long-term memory (user facts) manager for Yumii.

Uses LangGraph's native ``AsyncSqliteStore`` (``langgraph.store.sqlite``) so
facts are persisted as JSON documents in a local SQLite database.  Facts
survive across sessions and are injected into the system prompt on every new /
resumed session.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite
from langgraph.store.sqlite import AsyncSqliteStore

from yumii.core.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UserFact:
    """A single extracted fact about the user."""

    id: str
    fact: str
    category: str
    confidence: float
    session_id: str | None
    created_at: str

    @classmethod
    def from_item(cls, item: Any) -> "UserFact":
        """Build a ``UserFact`` from a LangGraph ``SearchItem`` / ``Item``."""
        val = item.value
        return cls(
            id=item.key,
            fact=val.get("fact", ""),
            category=val.get("category", "general"),
            confidence=val.get("confidence", 1.0),
            session_id=val.get("session_id"),
            created_at=str(item.created_at),
        )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


class MemoryManager:
    """Async CRUD for long-term user facts backed by LangGraph SQLite Store."""

    _NAMESPACE: tuple[str, ...] = ("facts",)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or str(
            Path.home() / ".yumii" / "memory" / "store.db"
        )
        self._store: AsyncSqliteStore | None = None
        self._conn: aiosqlite.Connection | None = None

    async def _ensure_store(self) -> AsyncSqliteStore:
        """Lazy-connect to the SQLite store and run migrations."""
        if self._store is None:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(self._db_path, isolation_level=None)
            self._store = AsyncSqliteStore(self._conn)
            await self._store.setup()
            log.debug("memory_store_ready", path=self._db_path)
        return self._store

    async def close(self) -> None:
        """Close the underlying database connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            self._store = None
            log.debug("memory_store_closed")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def store_fact(
        self,
        fact: str,
        *,
        category: str = "general",
        confidence: float = 1.0,
        session_id: str | None = None,
    ) -> str:
        """Store a new fact and return its store key."""
        store = await self._ensure_store()
        key = str(uuid.uuid4())
        await store.aput(
            self._NAMESPACE,
            key,
            {
                "fact": fact,
                "category": category,
                "confidence": confidence,
                "session_id": session_id,
            },
        )
        log.info(
            "fact_stored",
            fact_key=key,
            category=category,
            fact_preview=fact[:60],
        )
        return key

    async def update_fact(self, fact_id: str, fact: str) -> None:
        """Update the text of an existing fact."""
        store = await self._ensure_store()
        item = await store.aget(self._NAMESPACE, fact_id)
        if item is None:
            log.warning("update_fact_missing", fact_id=fact_id)
            return
        value = dict(item.value)
        value["fact"] = fact
        await store.aput(self._NAMESPACE, fact_id, value)
        log.info("fact_updated", fact_id=fact_id)

    async def delete_fact(self, fact_id: str) -> None:
        """Remove a single fact."""
        store = await self._ensure_store()
        await store.adelete(self._NAMESPACE, fact_id)
        log.info("fact_deleted", fact_id=fact_id)

    async def clear_all_facts(self) -> None:
        """Wipe every stored fact (used by /forget)."""
        store = await self._ensure_store()
        items = await store.asearch(self._NAMESPACE, limit=10000)
        for item in items:
            await store.adelete(self._NAMESPACE, item.key)
        log.info("all_facts_cleared", count=len(items))

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_facts(
        self,
        *,
        categories: list[str] | None = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> list[UserFact]:
        """Retrieve facts, optionally filtered by category and confidence."""
        store = await self._ensure_store()
        # The SQLite store supports equality filters but not range operators
        # (e.g. ``confidence >= 0.5``).  Because the fact corpus is small
        # (typically <1 000 items) we fetch generously and filter in-memory.
        items = await store.asearch(self._NAMESPACE, limit=limit * 2 if categories else limit)
        facts: list[UserFact] = []
        for item in items:
            uf = UserFact.from_item(item)
            if categories and uf.category not in categories:
                continue
            if uf.confidence < min_confidence:
                continue
            facts.append(uf)
            if len(facts) >= limit:
                break

        # Newest first (consistent with the previous custom schema)
        facts.sort(key=lambda f: f.created_at, reverse=True)
        return facts

    async def get_facts_formatted(
        self,
        *,
        categories: list[str] | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> str:
        """Return a markdown bullet list of facts suitable for a prompt."""
        facts = await self.get_facts(
            categories=categories,
            min_confidence=min_confidence,
            limit=limit,
        )
        if not facts:
            return ""
        lines = ["Things you know about the user:"]
        for f in facts:
            lines.append(f"  • {f.fact}")
        return "\n".join(lines)

    async def get_facts_raw(
        self,
        *,
        categories: list[str] | None = None,
        limit: int = 50,
    ) -> list[str]:
        """Return just the fact strings (no metadata)."""
        facts = await self.get_facts(categories=categories, limit=limit)
        return [f.fact for f in facts]

    # ------------------------------------------------------------------
    # Extraction (stub — filled in v1.1)
    # ------------------------------------------------------------------

    async def extract_facts_from_messages(
        self,
        messages: list[Any],
        session_id: str,
    ) -> list[str]:
        """Analyse a list of messages and extract new facts about the user.

        This is a **stub** for v0.2.0.  In v1.1 it will call a cheap LLM
        (e.g. llama-3.1-8b via Groq) to extract facts and then call
        :meth:`store_fact` for each one.

        Returns an empty list so that nothing happens until the feature
        is fully wired.
        """
        log.debug("fact_extraction_stub", message_count=len(messages))
        return []


# Global singleton — safe because all methods are async and the store is
# lazily connected on first use.
memory_manager = MemoryManager()
