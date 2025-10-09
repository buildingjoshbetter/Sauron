"""
Enhanced contextual memory system with summarization and fact extraction.
Beats GPT Plus memory by storing structured facts + full conversation history.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List
from datetime import datetime


class MemorySystem:
    """
    Advanced memory system:
    - Stores full conversation history (unlimited)
    - Auto-generates summaries every N messages
    - Extracts and stores facts (names, preferences, context)
    - Smart context window: recent + relevant facts
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.conv_file = data_dir / "conversation.json"
        self.facts_file = data_dir / "facts.json"
        self.summaries_file = data_dir / "summaries.json"
        
        self.conversation: List[Dict[str, str]] = []
        self.facts: Dict[str, str] = {}  # key: fact, value: context
        self.summaries: List[Dict] = []  # rolling summaries of conversation chunks
        
        self._load()
        self._ensure_user_profile()
    
    def _load(self):
        """Load all memory from disk."""
        # Load conversation
        if self.conv_file.exists():
            try:
                with open(self.conv_file, "r") as f:
                    data = json.load(f)
                self.conversation = data.get("messages", [])
                logging.info("loaded %d messages from conversation history", len(self.conversation))
            except Exception as e:
                logging.warning("failed to load conversation: %s", e)
        
        # Load facts
        if self.facts_file.exists():
            try:
                with open(self.facts_file, "r") as f:
                    self.facts = json.load(f)
                logging.info("loaded %d facts from memory", len(self.facts))
            except Exception as e:
                logging.warning("failed to load facts: %s", e)
        
        # Load summaries
        if self.summaries_file.exists():
            try:
                with open(self.summaries_file, "r") as f:
                    self.summaries = json.load(f)
                logging.info("loaded %d conversation summaries", len(self.summaries))
            except Exception as e:
                logging.warning("failed to load summaries: %s", e)
    
    def save(self):
        """Save all memory to disk."""
        try:
            with open(self.conv_file, "w") as f:
                json.dump({"messages": self.conversation}, f, indent=2)
            with open(self.facts_file, "w") as f:
                json.dump(self.facts, f, indent=2)
            with open(self.summaries_file, "w") as f:
                json.dump(self.summaries, f, indent=2)
        except Exception as e:
            logging.warning("failed to save memory: %s", e)
    
    def add_message(self, role: str, content: str):
        """Add a message to conversation history."""
        self.conversation.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def extract_facts(self, llm_response: str, user_input: str):
        """
        Extract facts from conversation.
        Uses simple pattern matching + full text indexing for recall.
        """
        lower_input = user_input.lower()
        timestamp_key = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Extract name mentions
        if "my name is" in lower_input or "i'm " in lower_input or "i am " in lower_input:
            self.facts[f"name_mention_{timestamp_key}"] = user_input
        
        # Extract project mentions
        if "project" in lower_input:
            self.facts[f"project_{timestamp_key}"] = user_input
        
        # Extract preferences
        if "i like" in lower_input or "i prefer" in lower_input or "i hate" in lower_input or "i don't like" in lower_input:
            self.facts[f"preference_{timestamp_key}"] = user_input
        
        # Extract future plans
        if "i'm going to" in lower_input or "i will" in lower_input or "planning to" in lower_input:
            self.facts[f"plan_{timestamp_key}"] = user_input
        
        # Extract general mentions (things you talk about in passing)
        # Store significant user statements that aren't just questions
        words = user_input.split()
        if len(words) >= 5 and not user_input.strip().endswith("?"):
            # Check if it contains meaningful content words
            significant_words = ["working", "building", "thinking", "tried", "found", "learned", "realized", "started", "finished"]
            if any(word in lower_input for word in significant_words):
                self.facts[f"mention_{timestamp_key}"] = user_input
        
        # Keep last 500 facts (increased from 200)
        if len(self.facts) > 500:
            # Remove oldest facts, but preserve user profile facts
            profile_keys = [k for k in self.facts.keys() if k.startswith("user_")]
            other_facts = [(k, v) for k, v in self.facts.items() if not k.startswith("user_")]
            sorted_facts = sorted(other_facts, key=lambda x: x[0], reverse=True)
            
            # Keep profile facts + most recent 400 other facts
            self.facts = dict([(k, self.facts[k]) for k in profile_keys] + sorted_facts[:400])
    
    def build_context_window(self, max_recent: int = 20, current_query: str = "") -> List[Dict[str, str]]:
        """
        Build smart context window for LLM:
        - Recent N messages (for immediate context)
        - Relevant past messages (semantic search through all history)
        - Relevant facts (for long-term memory)
        
        Returns list of messages ready for LLM.
        """
        context = []
        
        # Add recent conversation (always)
        recent_msgs = self.conversation[-max_recent:] if len(self.conversation) > max_recent else self.conversation
        recent_timestamps = {msg.get("timestamp", "") for msg in recent_msgs}
        
        # If there's a current query, search for relevant past messages
        if current_query and len(self.conversation) > max_recent:
            relevant_past = self._search_relevant_messages(current_query, exclude_timestamps=recent_timestamps, max_results=5)
            if relevant_past:
                # Add a marker message to separate past context from recent
                context.append({
                    "role": "system",
                    "content": f"[Relevant past context from previous conversations:]"
                })
                context.extend(relevant_past)
        
        # Add recent conversation
        context.extend(recent_msgs)
        
        return context
    
    def _search_relevant_messages(self, query: str, exclude_timestamps: set, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Simple keyword-based semantic search through conversation history.
        Returns relevant messages from the past.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # Remove common words that don't help with relevance
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "is", "are", "was", "were", "what", "when", "where", "who", "why", "how"}
        query_words = query_words - stop_words
        
        if not query_words:
            return []
        
        # Score all messages by keyword overlap
        scored_messages = []
        for msg in self.conversation:
            # Skip recent messages (already in context)
            if msg.get("timestamp", "") in exclude_timestamps:
                continue
            
            # Skip system messages
            if msg.get("role") == "system":
                continue
            
            content = msg.get("content", "").lower()
            content_words = set(content.split())
            
            # Calculate overlap score
            overlap = len(query_words & content_words)
            if overlap > 0:
                scored_messages.append((overlap, msg))
        
        # Sort by score and return top results
        scored_messages.sort(reverse=True, key=lambda x: x[0])
        return [msg for score, msg in scored_messages[:max_results]]
    
    def get_memory_summary(self, current_query: str = "") -> str:
        """
        Generate a memory summary to inject into system prompt.
        This gives SAURON context about past interactions.
        Optionally filters for relevant facts based on current query.
        """
        if not self.facts and not self.summaries:
            return ""
        
        parts = []
        
        # Add key facts (filtered for relevance if query provided)
        if self.facts:
            relevant_facts = self._get_relevant_facts(current_query) if current_query else list(self.facts.items())[-15:]
            
            if relevant_facts:
                parts.append("Key facts from memory:")
                for key, value in relevant_facts:
                    # Skip user profile facts (already in base system prompt)
                    if not key.startswith("user_"):
                        parts.append(f"- {value}")
        
        # Add recent summaries
        if self.summaries:
            parts.append("\nRecent conversation summaries:")
            for summary in self.summaries[-3:]:  # Last 3 summaries
                parts.append(f"- {summary.get('summary', '')}")
        
        return "\n".join(parts)
    
    def _get_relevant_facts(self, query: str, max_facts: int = 15) -> List[tuple]:
        """
        Find facts relevant to the current query using keyword matching.
        Returns list of (key, value) tuples.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # Remove common words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "is", "are", "was", "were", "what", "when", "where", "who", "why", "how"}
        query_words = query_words - stop_words
        
        if not query_words:
            # No query words, return recent facts
            return list(self.facts.items())[-max_facts:]
        
        # Score facts by keyword overlap
        scored_facts = []
        for key, value in self.facts.items():
            value_lower = value.lower()
            value_words = set(value_lower.split())
            overlap = len(query_words & value_words)
            
            # Boost score if query words appear in the fact
            if any(word in value_lower for word in query_words):
                overlap += 2
            
            if overlap > 0:
                scored_facts.append((overlap, key, value))
        
        # Sort by relevance and return top facts
        scored_facts.sort(reverse=True, key=lambda x: x[0])
        return [(key, value) for score, key, value in scored_facts[:max_facts]]
    
    def should_summarize(self) -> bool:
        """Check if we should generate a summary (every 50 messages)."""
        return len(self.conversation) % 50 == 0 and len(self.conversation) > 0
    
    def add_summary(self, summary: str):
        """Add a conversation summary."""
        self.summaries.append({
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
            "message_count": len(self.conversation)
        })
        
        # Keep only last 20 summaries
        if len(self.summaries) > 20:
            self.summaries = self.summaries[-20:]
    
    def _ensure_user_profile(self):
        """Ensure Josh's profile is stored as foundational facts."""
        profile_facts = {
            "user_name": "Josh Adler, 26, engineer and entrepreneur",
            "user_personality": "Direct, analytical, impatient with inefficiency. Values truth over politeness. Perfectionist in function, minimalist in form.",
            "user_communication": "Wants concise, conversational responses. No filler. Confident, slightly sardonic tone. Sparring partner, not assistant.",
            "user_adhd": "Highly ADHD - fast context switching, obsessive focus when locked in. Learns by doing, treats failure as data.",
            "user_interests": "Hardware/robotics (drones, robots, CNCs, rockets), AI/autonomy, biology/optimization, philosophy/systems thinking, sleek minimal aesthetics",
            "user_projects": "Building intelligent home devices that observe, listen, and understand - not just automate",
            "user_expectations": "System should adapt to his rhythm, predict context, anticipate patterns. Occasionally push back when logic demands. Extension of his mind, not a butler.",
            "user_home_philosophy": "Home is a lab - a living system. Values autonomy, feedback loops, self-improvement.",
            "user_cycle": "Operates in intense build sprints followed by brief reflection or travel resets",
            "user_friction": "Enjoys friction - it sharpens thought. Wants tools that feel alive - fast, predictive, adaptable."
        }
        
        # Only add if not already present
        for key, value in profile_facts.items():
            if key not in self.facts:
                self.facts[key] = value
                logging.info("initialized user profile fact: %s", key)

