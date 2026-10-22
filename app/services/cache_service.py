"""
Deterministic Caching & Audit Logging Service for Plan Your Future Engine.
Provides SHA-256 scenario hashing, 24-hour TTL caching, automatic invalidation,
and historical run logs.
"""

import json
import hashlib
import time
from typing import Dict, Any, Optional, List
from threading import Lock
from datetime import datetime, timezone


class ScenarioCacheService:
    """
    Thread-safe in-memory scenario cache with deterministic SHA-256 hashing,
    24-hour TTL, and persistent execution history log.
    """

    TTL_SECONDS = 86400  # 24 Hours strict TTL

    def __init__(self):
        self._lock = Lock()
        self._cache: Dict[str, Dict[str, Any]] = {}  # hash -> { "data": dict, "expires_at": float, "cached_at": str }
        self._history_log: List[Dict[str, Any]] = []  # chronological calculation audit log
        self._hits = 0
        self._misses = 0

    @classmethod
    def compute_hash(
        cls,
        inputs: Dict[str, Any],
        assumptions: Dict[str, Any],
        profile_version: str = "v1.0",
        product_rules_version: str = "2026.1",
        prompt_version: str = "v1.2"
    ) -> str:
        """
        Computes deterministic SHA-256 hash across sorted inputs, assumptions,
        and version identifiers. Guarantees that any change to inputs, rates, or
        rules invalidates the previous hash.
        """
        canonical_payload = {
            "assumptions": assumptions,
            "inputs": inputs,
            "product_rules_version": product_rules_version,
            "profile_version": profile_version,
            "prompt_version": prompt_version
        }
        canonical_str = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def get(self, scenario_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached result if present and within 24-hour TTL."""
        with self._lock:
            entry = self._cache.get(scenario_hash)
            if not entry:
                self._misses += 1
                return None

            now = time.time()
            if now > entry["expires_at"]:
                # Evict expired entry
                del self._cache[scenario_hash]
                self._misses += 1
                return None

            self._hits += 1
            return entry["data"]

    def set(
        self,
        scenario_hash: str,
        result_data: Dict[str, Any],
        request_id: Optional[str] = None,
        summary: Optional[str] = None
    ) -> None:
        """Caches result with 24-hour TTL and records chronological run audit."""
        now = time.time()
        iso_now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self._cache[scenario_hash] = {
                "data": result_data,
                "expires_at": now + self.TTL_SECONDS,
                "cached_at": iso_now
            }

            # Append to execution history log
            self._history_log.append({
                "scenario_hash": scenario_hash,
                "request_id": request_id,
                "timestamp": iso_now,
                "summary": summary
            })

            # Keep audit log capped at latest 500 runs
            if len(self._history_log) > 500:
                self._history_log.pop(0)

    def invalidate(self, scenario_hash: str) -> bool:
        """Explicitly invalidates an entry by scenario hash."""
        with self._lock:
            if scenario_hash in self._cache:
                del self._cache[scenario_hash]
                return True
            return False

    def clear(self) -> None:
        """Clears entire cache."""
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Returns cache telemetry and statistics."""
        with self._lock:
            now = time.time()
            valid_count = sum(1 for e in self._cache.values() if e["expires_at"] > now)
            total_requests = self._hits + self._misses
            hit_ratio = round((self._hits / total_requests * 100), 1) if total_requests > 0 else 0.0

            return {
                "active_cached_scenarios": valid_count,
                "cache_hits": self._hits,
                "cache_misses": self._misses,
                "hit_ratio_pct": hit_ratio,
                "ttl_hours": 24,
                "total_history_runs_recorded": len(self._history_log)
            }

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns latest execution history logs."""
        with self._lock:
            return list(reversed(self._history_log[-limit:]))


# Global singleton instance
plan_future_cache = ScenarioCacheService()
