"""
Tiered memory system with 3 levels of recall speed vs depth.
Optimizes for fast local queries with fallback to deep NAS search.
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class TieredMemory:
    """
    3-tier memory architecture:
    
    Tier 1 (Local Pi): Fast, recent, high-detail
    - Last 7 days of summaries
    - Last 1000 messages
    - 500 most recent facts
    - Size: ~10-15GB
    - Query: ~0.5s
    
    Tier 2 (NAS Medium): Moderate speed, medium detail
    - Last 3 months of medium summaries
    - All messages (full history)
    - All facts (10,000+)
    - Size: ~50GB
    - Query: ~2s
    
    Tier 3 (NAS Deep): Slow, unlimited, low-detail
    - Full history (years)
    - Low-level summaries (highly compressed)
    - Raw audio/video archives
    - Size: Unlimited
    - Query: ~5-10s
    """
    
    def __init__(self, local_dir: Path, nas_dir: Path):
        self.local_dir = local_dir
        self.nas_dir = nas_dir
        
        # Tier 1: Local cache (Pi SD card)
        self.tier1_dir = local_dir / "tier1_cache"
        self.tier1_dir.mkdir(exist_ok=True)
        
        # Tier 2: NAS medium (full conversation + medium summaries)
        self.tier2_dir = nas_dir / "tier2_medium"
        self.tier2_dir.mkdir(exist_ok=True)
        
        # Tier 3: NAS deep (low-level summaries + archives)
        self.tier3_dir = nas_dir / "tier3_deep"
        self.tier3_dir.mkdir(exist_ok=True)
    
    def search_tiered(self, query: str, max_results: int = 5) -> Dict:
        """
        Search across all tiers, starting with fastest.
        Returns results with tier metadata.
        """
        results = {
            "query": query,
            "tier": None,
            "results": [],
            "search_time_ms": 0,
            "searched_tiers": []
        }
        
        import time
        start_time = time.time()
        
        # Try Tier 1 first (local, fast)
        logging.info(f"Searching Tier 1 (local) for: {query[:50]}")
        tier1_results = self._search_tier1(query, max_results)
        results["searched_tiers"].append("tier1")
        
        if tier1_results:
            results["tier"] = "tier1_local"
            results["results"] = tier1_results
            results["search_time_ms"] = int((time.time() - start_time) * 1000)
            logging.info(f"Found {len(tier1_results)} results in Tier 1 ({results['search_time_ms']}ms)")
            return results
        
        # Try Tier 2 (NAS medium detail)
        logging.info(f"Tier 1 empty, searching Tier 2 (NAS medium) for: {query[:50]}")
        tier2_results = self._search_tier2(query, max_results)
        results["searched_tiers"].append("tier2")
        
        if tier2_results:
            results["tier"] = "tier2_nas_medium"
            results["results"] = tier2_results
            results["search_time_ms"] = int((time.time() - start_time) * 1000)
            logging.info(f"Found {len(tier2_results)} results in Tier 2 ({results['search_time_ms']}ms)")
            return results
        
        # Try Tier 3 (NAS deep archive)
        logging.info(f"Tier 2 empty, searching Tier 3 (NAS deep) for: {query[:50]}")
        tier3_results = self._search_tier3(query, max_results)
        results["searched_tiers"].append("tier3")
        
        if tier3_results:
            results["tier"] = "tier3_nas_deep"
            results["results"] = tier3_results
            results["search_time_ms"] = int((time.time() - start_time) * 1000)
            logging.info(f"Found {len(tier3_results)} results in Tier 3 ({results['search_time_ms']}ms)")
            return results
        
        # Nothing found
        results["search_time_ms"] = int((time.time() - start_time) * 1000)
        logging.warning(f"No results found in any tier for: {query[:50]}")
        return results
    
    def _search_tier1(self, query: str, max_results: int) -> List[Dict]:
        """
        Search Tier 1 (local Pi cache).
        High-detail summaries from last 7 days + recent conversations.
        """
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # Remove stop words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "is", "are", "was", "were"}
        query_words = query_words - stop_words
        
        if not query_words:
            return []
        
        # Search recent summaries (last 7 days)
        summaries_file = self.tier1_dir / "recent_summaries.json"
        if summaries_file.exists():
            try:
                with open(summaries_file, "r") as f:
                    summaries = json.load(f)
                
                for summary in summaries[-7:]:  # Last 7 days
                    content = summary.get("summary", "").lower()
                    score = sum(1 for word in query_words if word in content)
                    
                    if score > 0:
                        results.append({
                            "date": summary.get("date", ""),
                            "content": summary.get("summary", ""),
                            "score": score,
                            "type": "tier1_summary"
                        })
            except Exception as e:
                logging.error(f"Failed to search Tier 1 summaries: {e}")
        
        # Search recent messages (last 1000)
        messages_file = self.tier1_dir / "recent_messages.json"
        if messages_file.exists():
            try:
                with open(messages_file, "r") as f:
                    messages = json.load(f)
                
                for msg in messages[-1000:]:
                    content = msg.get("content", "").lower()
                    score = sum(1 for word in query_words if word in content)
                    
                    if score > 0:
                        results.append({
                            "timestamp": msg.get("timestamp", ""),
                            "content": msg.get("content", ""),
                            "score": score,
                            "type": "tier1_message"
                        })
            except Exception as e:
                logging.error(f"Failed to search Tier 1 messages: {e}")
        
        # Sort by relevance
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]
    
    def _search_tier2(self, query: str, max_results: int) -> List[Dict]:
        """
        Search Tier 2 (NAS medium detail).
        Medium summaries from last 3 months + full conversation history.
        """
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "is", "are", "was", "were"}
        query_words = query_words - stop_words
        
        if not query_words:
            return []
        
        # Search medium summaries (last 3 months)
        summaries_dir = self.tier2_dir / "medium_summaries"
        if summaries_dir.exists():
            cutoff_date = datetime.now() - timedelta(days=90)
            
            for summary_file in sorted(summaries_dir.glob("*.json")):
                try:
                    with open(summary_file, "r") as f:
                        summary = json.load(f)
                    
                    # Check if within last 3 months
                    date_str = summary.get("date", "")
                    try:
                        summary_date = datetime.fromisoformat(date_str)
                        if summary_date < cutoff_date:
                            continue
                    except:
                        pass
                    
                    content = summary.get("summary", "").lower()
                    score = sum(1 for word in query_words if word in content)
                    
                    if score > 0:
                        results.append({
                            "date": date_str,
                            "content": summary.get("summary", ""),
                            "score": score,
                            "type": "tier2_medium_summary"
                        })
                except Exception as e:
                    logging.error(f"Failed to read summary {summary_file}: {e}")
        
        # Sort by relevance
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]
    
    def _search_tier3(self, query: str, max_results: int) -> List[Dict]:
        """
        Search Tier 3 (NAS deep archive).
        Low-level summaries (highly compressed) from full history.
        """
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "is", "are", "was", "were"}
        query_words = query_words - stop_words
        
        if not query_words:
            return []
        
        # Search low-level summaries (all history)
        summaries_dir = self.tier3_dir / "low_summaries"
        if summaries_dir.exists():
            for summary_file in sorted(summaries_dir.glob("*.json")):
                try:
                    with open(summary_file, "r") as f:
                        summary = json.load(f)
                    
                    content = summary.get("summary", "").lower()
                    score = sum(1 for word in query_words if word in content)
                    
                    if score > 0:
                        results.append({
                            "date": summary.get("date", ""),
                            "content": summary.get("summary", ""),
                            "score": score,
                            "type": "tier3_low_summary"
                        })
                except Exception as e:
                    logging.error(f"Failed to read deep summary {summary_file}: {e}")
        
        # Sort by relevance
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]
    
    def sync_tier1(self, memory_system):
        """
        Sync Tier 1 cache with latest data from memory system.
        Keep only last 7 days of summaries + last 1000 messages.
        """
        logging.info("Syncing Tier 1 cache...")
        
        # Sync recent summaries
        if memory_system.summaries:
            summaries_file = self.tier1_dir / "recent_summaries.json"
            recent_summaries = memory_system.summaries[-7:]  # Last 7 days
            with open(summaries_file, "w") as f:
                json.dump(recent_summaries, f, indent=2)
            logging.info(f"Synced {len(recent_summaries)} summaries to Tier 1")
        
        # Sync recent messages
        if memory_system.conversation:
            messages_file = self.tier1_dir / "recent_messages.json"
            recent_messages = memory_system.conversation[-1000:]  # Last 1000
            with open(messages_file, "w") as f:
                json.dump(recent_messages, f, indent=2)
            logging.info(f"Synced {len(recent_messages)} messages to Tier 1")
    
    def promote_to_tier2(self, data: Dict, summary_type: str):
        """
        Promote data from Tier 1 to Tier 2 (medium detail).
        Called during daily cleanup.
        """
        tier2_summaries = self.tier2_dir / "medium_summaries"
        tier2_summaries.mkdir(exist_ok=True)
        
        date_key = data.get("date", datetime.now().strftime("%Y-%m-%d"))
        filename = f"{summary_type}_{date_key}.json"
        
        with open(tier2_summaries / filename, "w") as f:
            json.dump(data, f, indent=2)
        
        logging.info(f"Promoted {summary_type} to Tier 2: {filename}")
    
    def compress_to_tier3(self, data: Dict, summary_type: str):
        """
        Compress and archive data to Tier 3 (low detail).
        Called when Tier 2 exceeds size limit (3 months).
        """
        tier3_summaries = self.tier3_dir / "low_summaries"
        tier3_summaries.mkdir(exist_ok=True)
        
        # Create highly compressed summary
        compressed = {
            "date": data.get("date", ""),
            "summary": self._compress_summary(data.get("summary", "")),
            "type": summary_type,
            "original_size": len(str(data))
        }
        
        date_key = data.get("date", datetime.now().strftime("%Y-%m-%d"))
        filename = f"{summary_type}_compressed_{date_key}.json"
        
        with open(tier3_summaries / filename, "w") as f:
            json.dump(compressed, f)
        
        logging.info(f"Compressed to Tier 3: {filename} (reduction: {len(str(compressed))/len(str(data))*100:.1f}%)")
    
    def _compress_summary(self, summary: str) -> str:
        """
        Ultra-compress summary for Tier 3.
        Extract only key entities, actions, and timestamps.
        """
        # Simple compression: keep first sentence + keywords
        sentences = summary.split(". ")
        if not sentences:
            return summary
        
        # Keep first sentence + extract key phrases
        compressed = sentences[0]
        
        # Extract entities (capitalized words)
        entities = [word for word in summary.split() if word[0].isupper() and len(word) > 3]
        if entities:
            compressed += f". Key: {', '.join(set(entities[:10]))}"
        
        return compressed

