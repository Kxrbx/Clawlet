"""
Memory management for agent context and history.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from pathlib import Path
import re

from loguru import logger


AUTOGEN_START = "<!-- CLAWLET_MEMORY_AUTOGEN_START -->"
AUTOGEN_END = "<!-- CLAWLET_MEMORY_AUTOGEN_END -->"


@dataclass
class MemoryEntry:
    """A single memory entry."""
    key: str
    value: str
    category: str = "general"
    importance: int = 5  # 1-10 scale
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class MemoryManager:
    """
    Manages agent memory and context.
    
    Memory types:
    - Short-term: Recent conversation history
    - Long-term: Persistent memories stored in MEMORY.md
    - Working: Current task context
    """
    
    def __init__(self, workspace: Path, max_short_term: int = 50):
        """
        Initialize memory manager.
        
        Args:
            workspace: Path to workspace directory
            max_short_term: Maximum short-term memories to keep
        """
        self.workspace = workspace
        self.max_short_term = max_short_term
        
        self._short_term: list[MemoryEntry] = []
        self._long_term: dict[str, MemoryEntry] = {}
        self._working: dict[str, Any] = {}
        self._base_memory_content: str = ""
        
        # Load long-term memories from MEMORY.md
        self._load_long_term()
        
        logger.info(f"MemoryManager initialized with {len(self._long_term)} long-term memories")
    
    def _load_long_term(self) -> None:
        """Load long-term memories from MEMORY.md."""
        memory_file = self.workspace / "MEMORY.md"
        if not memory_file.exists():
            logger.debug(f"No MEMORY.md found at {memory_file}")
            return
        
        try:
            content = memory_file.read_text(encoding="utf-8")
            base_content, generated_content = self._split_memory_sections(content)
            self._base_memory_content = base_content.strip()
            self._long_term["__file__"] = MemoryEntry(
                key="__file__",
                value=content,
                category="system",
                importance=10,
            )
            self._load_structured_entries(generated_content or content)
        except Exception as e:
            logger.warning(f"Failed to load MEMORY.md: {e}")

    def _split_memory_sections(self, content: str) -> tuple[str, str]:
        """Split manual MEMORY.md content from the auto-generated section."""
        if AUTOGEN_START not in content or AUTOGEN_END not in content:
            return content, ""
        prefix, remainder = content.split(AUTOGEN_START, 1)
        generated, _suffix = remainder.split(AUTOGEN_END, 1)
        return prefix.rstrip(), generated.strip()

    def _load_structured_entries(self, content: str) -> None:
        """Parse generated markdown entries back into structured long-term memories."""
        current_category = "general"
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("## "):
                current_category = line[3:].strip().lower()
                continue
            m = re.match(r"- \*\*(.+?)\*\*: (.+)$", line)
            if not m:
                continue
            key = m.group(1).strip()
            value = m.group(2).strip()
            if key == "__file__":
                continue
            self._long_term[key] = MemoryEntry(
                key=key,
                value=value,
                category=current_category,
                importance=8,
            )
    
    def remember(self, key: str, value: str, category: str = "general", importance: int = 5) -> None:
        """
        Store something in short-term memory.
        
        Args:
            key: Memory key
            value: Memory value
            category: Category for organization
            importance: Importance level (1-10)
        """
        entry = MemoryEntry(
            key=key,
            value=value,
            category=category,
            importance=importance,
        )
        
        # Add to short-term
        self._short_term.append(entry)
        
        # Also add/update in long-term storage for persistence
        self._long_term[key] = entry
        
        # Trim short-term if needed
        if len(self._short_term) > self.max_short_term:
            # Remove lowest importance, oldest entries
            self._short_term.sort(key=lambda e: (e.importance, e.created_at), reverse=True)
            self._short_term = self._short_term[:self.max_short_term]
        
        logger.debug(f"Remembered: {key} (importance={importance})")
    
    def recall(self, key: str) -> Optional[str]:
        """
        Recall a memory by key.
        
        Checks short-term first, then long-term.
        
        Args:
            key: Memory key
            
        Returns:
            Memory value or None
        """
        # Check short-term (most recent first)
        for entry in reversed(self._short_term):
            if entry.key == key:
                return entry.value
        
        # Check long-term
        if key in self._long_term:
            return self._long_term[key].value
        
        return None
    
    def recall_by_category(self, category: str, limit: int = 10) -> list[MemoryEntry]:
        """
        Recall memories by category.
        
        Args:
            category: Category to filter by
            limit: Maximum entries to return
            
        Returns:
            List of memory entries
        """
        # Combine short-term and long-term
        all_memories = self._short_term + list(self._long_term.values())
        
        # Filter by category and sort by importance
        filtered = [m for m in all_memories if m.category == category]
        filtered.sort(key=lambda e: (e.importance, e.updated_at), reverse=True)
        
        return filtered[:limit]
    
    def forget(self, key: str) -> bool:
        """
        Remove a memory.
        
        Args:
            key: Memory key
            
        Returns:
            True if memory was removed
        """
        removed = False
        
        # Remove from short-term
        for i, entry in enumerate(self._short_term):
            if entry.key == key:
                self._short_term.pop(i)
                logger.debug(f"Forgot short-term memory: {key}")
                removed = True
                break  # key unique, stop after first
        
        # Remove from long-term
        if key in self._long_term:
            del self._long_term[key]
            logger.debug(f"Forgot long-term memory: {key}")
            removed = True
        
        return removed
    
    def set_working(self, key: str, value: Any) -> None:
        """Set a working memory value (current task context)."""
        self._working[key] = value
    
    def get_working(self, key: str, default: Any = None) -> Any:
        """Get a working memory value."""
        return self._working.get(key, default)
    
    def clear_working(self) -> None:
        """Clear all working memory."""
        self._working.clear()
    
    def get_context(self, max_entries: int = 20) -> str:
        """
        Build context string from memories.
        
        Args:
            max_entries: Maximum entries to include
            
        Returns:
            Formatted context string
        """
        # Combine and sort by importance
        all_memories = [m for m in (self._short_term + list(self._long_term.values())) if m.key != "__file__"]
        all_memories.sort(key=lambda e: e.importance, reverse=True)
        top_memories = all_memories[:max_entries]
        if not top_memories:
            return ""
        
        # Build context
        lines = ["## Relevant Memories\n"]
        for entry in top_memories:
            lines.append(f"- [{entry.category}] {entry.key}: {entry.value[:100]}...")
        
        return "\n".join(lines)

    def get_identity_memory(self) -> str:
        """Return only the manual identity memory section, excluding auto-generated memories."""
        return self._base_memory_content.strip()
    
    def save_long_term(self) -> None:
        """Save long-term memories to MEMORY.md."""
        memory_file = self.workspace / "MEMORY.md"
        
        try:
            lines: list[str] = []
            if self._base_memory_content:
                lines.append(self._base_memory_content.rstrip())
            
            # Group by category
            categories: dict[str, list[MemoryEntry]] = {}
            for entry in self._long_term.values():
                if entry.key == "__file__":
                    continue
                if entry.category not in categories:
                    categories[entry.category] = []
                categories[entry.category].append(entry)
            
            generated_lines = [AUTOGEN_START, "## Auto-Saved Memories"]
            for category, entries in sorted(categories.items()):
                generated_lines.append(f"\n## {category.title()}")
                for entry in sorted(entries, key=lambda e: e.importance, reverse=True):
                    generated_lines.append(f"- **{entry.key}**: {entry.value}")
            generated_lines.append(AUTOGEN_END)

            if lines:
                lines.append("")
            lines.extend(generated_lines)

            content = "\n".join(lines).rstrip() + "\n"
            memory_file.write_text(content, encoding="utf-8")
            self._long_term["__file__"] = MemoryEntry(
                key="__file__",
                value=content,
                category="system",
                importance=10,
            )
        
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")
    
    def get_stats(self) -> dict:
        """Get memory statistics."""
        return {
            "short_term_count": len(self._short_term),
            "long_term_count": len(self._long_term),
            "working_count": len(self._working),
            "categories": list(set(m.category for m in self._short_term + list(self._long_term.values()))),
        }
