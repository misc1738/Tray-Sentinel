"""In-memory cache layer for performance optimization."""
import threading
import time
from typing import Any, Optional, Callable
from dataclasses import dataclass
from collections import OrderedDict


@dataclass
class CacheEntry:
    """Cache entry with TTL support."""
    value: Any
    created_at: float
    ttl: Optional[int] = None  # seconds, None = no expiry
    hits: int = 0

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl is None:
            return False
        return (time.time() - self.created_at) > self.ttl


class Cache:
    """Thread-safe in-memory cache with TTL support."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.store: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = threading.RLock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0
        }

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, return None if not found or expired."""
        with self.lock:
            if key not in self.store:
                self.stats['misses'] += 1
                return None
            
            entry = self.store[key]
            
            # Check expiration
            if entry.is_expired():
                del self.store[key]
                self.stats['misses'] += 1
                return None
            
            # Move to end (LRU)
            self.store.move_to_end(key)
            entry.hits += 1
            self.stats['hits'] += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        with self.lock:
            # Remove if exists
            if key in self.store:
                del self.store[key]
            
            # Evict oldest if at capacity
            if len(self.store) >= self.max_size:
                oldest_key = next(iter(self.store))
                del self.store[oldest_key]
                self.stats['evictions'] += 1
            
            # Add new entry
            self.store[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl
            )
            self.stats['sets'] += 1

    def delete(self, key: str) -> None:
        """Delete key from cache."""
        with self.lock:
            if key in self.store:
                del self.store[key]
                self.stats['deletes'] += 1

    def clear(self) -> None:
        """Clear all entries."""
        with self.lock:
            self.store.clear()

    def get_or_set(self, key: str, factory: Callable, ttl: Optional[int] = None) -> Any:
        """Get value from cache or compute and set if missing."""
        value = self.get(key)
        if value is not None:
            return value
        
        # Compute new value
        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    def stats_summary(self) -> dict:
        """Get cache statistics."""
        with self.lock:
            hit_rate = 0
            total_requests = self.stats['hits'] + self.stats['misses']
            if total_requests > 0:
                hit_rate = self.stats['hits'] / total_requests * 100
            
            return {
                'size': len(self.store),
                'max_size': self.max_size,
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'hit_rate_percent': round(hit_rate, 2),
                'sets': self.stats['sets'],
                'deletes': self.stats['deletes'],
                'evictions': self.stats['evictions']
            }


# Global cache instance
_cache: Optional[Cache] = None


def get_cache(max_size: int = 1000) -> Cache:
    """Get or create global cache instance."""
    global _cache
    if _cache is None:
        _cache = Cache(max_size=max_size)
    return _cache


def reset_cache() -> None:
    """Reset cache (for testing)."""
    global _cache
    _cache = None
