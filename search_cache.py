"""
搜索缓存 — TTL内存缓存，避免重复LLM/搜索调用

用于优化:
  - smart_search: 相同查询30秒内不重复搜
  - deep_research: 相同查询120秒内不重复深度研究
  - tianshu状态: 10秒内不重复请求天枢

用法:
  from search_cache import cache_get, cache_set
  cached = cache_get("search:query_text")
  if not cached:
      result = smart_search(query)
      cache_set("search:query_text", result, ttl=30)
"""

import time, hashlib
from threading import Lock

_cache: dict = {}
_lock = Lock()
_stats = {"hits": 0, "misses": 0, "sets": 0}


def _make_key(prefix: str, value: str) -> str:
    """为缓存生成短键。"""
    h = hashlib.md5(value.encode()).hexdigest()[:12]
    return f"{prefix}:{h}"


def cache_get(key: str) -> tuple:
    """获取缓存。返回 (value, age_seconds) 或 (None, 0)。"""
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            _stats["misses"] += 1
            return None, 0
        value, expiry = entry[0], entry[1]
        if time.time() > expiry:
            del _cache[key]
            _stats["misses"] += 1
            return None, 0
        _stats["hits"] += 1
        age = time.time() - (expiry - entry[2]) if len(entry) > 2 else 0.01
        return value, max(age, 0.01)


def cache_set(key: str, value: str, ttl: int = 30) -> None:
    """设置缓存，TTL秒后过期。"""
    with _lock:
        _cache[key] = (value, time.time() + ttl, ttl)
        _stats["sets"] += 1
        # LRU清理: 超过500条淘汰最旧100条
        if len(_cache) > 500:
            items = sorted(_cache.items(), key=lambda x: x[1][1])
            for old_key, _ in items[:100]:
                del _cache[old_key]


def cache_search(query: str, search_fn, ttl: int = 30) -> str:
    """搜索包装器: 命中缓存直接返回, 否则执行搜索并缓存。"""
    key = _make_key("search", query)
    cached, age = cache_get(key)
    if cached is not None:
        return cached
    result = search_fn()
    if result and len(str(result)) > 20:
        cache_set(key, str(result), ttl=ttl)
    return result


def cache_stats() -> dict:
    """缓存统计。"""
    with _lock:
        return {**_stats, "size": len(_cache)}
