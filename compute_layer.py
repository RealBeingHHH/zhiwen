"""
计算层 — 异步计算·缓存·后台线程池

把 Benford、熵场、TF-IDF、模拟等重计算从请求线程中拆出来。
结果缓存 + TTL，相同输入直接返回。

架构:
  请求 → compute("benford", data) → 检查缓存
    ├─ 命中 → 立即返回 (< 1ms)
    └─ 未命中 → 提交线程池 → 异步计算 → 缓存 → 返回

用法:
  from compute_layer import compute, compute_async, ComputeLayer
  result = compute("benford", data_text)
  future = compute_async("fiscal_sim", params)
"""

import time, hashlib, json, threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor, Future
from functools import partial

BASE = Path(__file__).parent


# ════════════════════════════════════════════════════════
# 计算注册表
# ════════════════════════════════════════════════════════

@dataclass
class ComputeFunction:
    """一个可缓存的计算函数。"""
    name: str
    fn: Callable
    ttl: float = 60.0          # 缓存TTL (秒)
    max_workers: int = 2       # 最大并发


# 注册的计算函数
_COMPUTE_REGISTRY: dict[str, ComputeFunction] = {}


def register(name: str, ttl: float = 60.0):
    """装饰器: 注册计算函数。"""
    def decorator(fn):
        _COMPUTE_REGISTRY[name] = ComputeFunction(name=name, fn=fn, ttl=ttl)
        return fn
    return decorator


# ════════════════════════════════════════════════════════
# 计算层引擎
# ════════════════════════════════════════════════════════

class ComputeLayer:
    """异步计算层 — 缓存 + 线程池。"""

    def __init__(self):
        self._cache: dict[str, tuple] = {}     # key → (result, expiry)
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=6)
        self._futures: dict[str, Future] = {}  # pending computations
        self._stats = {"hits": 0, "misses": 0, "computes": 0}

    def compute(self, name: str, *args, **kwargs) -> any:
        """
        同步计算 (阻塞但优先缓存)。

        如果缓存命中 → 立即返回。
        如果缓存未命中 → 同步计算并缓存。
        """
        cache_key = self._make_key(name, args, kwargs)

        # 缓存检查
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and time.time() < cached[1]:
                self._stats["hits"] += 1
                return cached[0]

        self._stats["misses"] += 1

        # 执行计算
        func = _COMPUTE_REGISTRY.get(name)
        if not func:
            return None

        result = func.fn(*args, **kwargs)
        self._stats["computes"] += 1

        # 缓存
        with self._lock:
            self._cache[cache_key] = (result, time.time() + func.ttl)
            if len(self._cache) > 200:
                self._evict_oldest()

        return result

    def compute_async(self, name: str, *args, **kwargs) -> Future:
        """
        异步计算 (不阻塞)。

        返回 Future，可后续 .result() 获取。
        """
        cache_key = self._make_key(name, args, kwargs)

        # 缓存检查
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and time.time() < cached[1]:
                self._stats["hits"] += 1
                future: Future = Future()
                future.set_result(cached[0])
                return future

            # 已有相同计算在进行中
            if cache_key in self._futures:
                return self._futures[cache_key]

        self._stats["misses"] += 1

        # 提交异步计算
        func = _COMPUTE_REGISTRY.get(name)
        if not func:
            future = Future()
            future.set_result(None)
            return future

        future = self._executor.submit(self._compute_and_cache, name, func,
                                        cache_key, args, kwargs)
        with self._lock:
            self._futures[cache_key] = future

        return future

    def precompute(self, name: str, *args, **kwargs) -> None:
        """预热: 后台计算并缓存, 不等待结果。"""
        self.compute_async(name, *args, **kwargs)

    def stats(self) -> dict:
        with self._lock:
            return {**self._stats, "cache_size": len(self._cache),
                    "pending": len(self._futures)}

    def _compute_and_cache(self, name: str, func: ComputeFunction,
                           cache_key: str, args: tuple, kwargs: dict) -> any:
        """执行计算并缓存结果。"""
        try:
            result = func.fn(*args, **kwargs)
            with self._lock:
                self._cache[cache_key] = (result, time.time() + func.ttl)
                self._futures.pop(cache_key, None)
                if len(self._cache) > 200:
                    self._evict_oldest()
            return result
        except Exception as e:
            with self._lock:
                self._futures.pop(cache_key, None)
            raise e

    def _make_key(self, name: str, args: tuple, kwargs: dict) -> str:
        raw = f"{name}:{str(args)[:200]}:{str(sorted(kwargs.items()))[:200]}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def _evict_oldest(self):
        if not self._cache:
            return
        oldest = min(self._cache.items(), key=lambda x: x[1][1])
        del self._cache[oldest[0]]


# ════════════════════════════════════════════════════════
# 注册的计算函数
# ════════════════════════════════════════════════════════

@register("benford", ttl=120)
def compute_benford(data_text: str) -> dict:
    """Benford定律检测 (120s缓存)。"""
    from voyager_auth import benford_check
    return benford_check(data_text)


@register("entropy", ttl=120)
def compute_entropy(data_text: str) -> dict:
    """熵场检测 (120s缓存)。"""
    from voyager_auth import entropy_field_check
    return entropy_field_check(data_text)


@register("authenticity", ttl=60)
def compute_authenticity(data_text: str, query: str = "") -> dict:
    """织星真实性三合一 (60s缓存)。"""
    from voyager_auth import VoyagerAuthenticity
    return VoyagerAuthenticity.verify(data_text, query)


@register("relations", ttl=60)
def compute_relations(data_text: str) -> dict:
    """关系完整性验证 (60s缓存)。"""
    from relation_integrity import verify_relations
    return verify_relations(data_text)


@register("tfidf_build", ttl=300)
def compute_tfidf_build(docs: list) -> dict:
    """TF-IDF索引构建 (300s缓存)。"""
    from matrix_store import TFIDFVectorizer
    vec = TFIDFVectorizer()
    vec.fit(docs)
    return {"vocab_size": len(vec.vocabulary), "doc_count": len(docs)}


@register("fiscal_sim", ttl=300)
def compute_fiscal_sim(params: dict = None) -> dict:
    """财政模拟 (300s缓存, 重计算)。"""
    from fiscal_sim import run_full_simulation
    return run_full_simulation()


# ════════════════════════════════════════════════════════
# 全局单例 + 快捷接口
# ════════════════════════════════════════════════════════

_compute_layer: Optional[ComputeLayer] = None


def get_compute_layer() -> ComputeLayer:
    global _compute_layer
    if _compute_layer is None:
        _compute_layer = ComputeLayer()
    return _compute_layer


def compute(name: str, *args, **kwargs) -> any:
    """快捷: 同步计算 (缓存优先)。"""
    return get_compute_layer().compute(name, *args, **kwargs)


def compute_async(name: str, *args, **kwargs) -> Future:
    """快捷: 异步计算。"""
    return get_compute_layer().compute_async(name, *args, **kwargs)


def precompute(name: str, *args, **kwargs) -> None:
    """快捷: 预热计算。"""
    get_compute_layer().precompute(name, *args, **kwargs)
