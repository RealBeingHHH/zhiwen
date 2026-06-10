"""
纹路记忆 — 知纹的研究模式持久化

不是存聊天记录。是存纹路——问题分解的结构、推理链的形状。
下次遇到延续问题，知纹不是从零分解，而是"这个纹路我见过"。

存储内容:
  纹路节点: 子问题文本 · DAG位置 · 证据评分 · 推理链
  纹路边:   依赖关系 · 问题延续关系 · 相似度

检索:
  新问题 → 向量相似匹配 → 找到最近的纹路 → 复用结构
  追问检测: 新问题是否延续上一轮 → 自动继承DAG

用法:
  from pattern_memory import PatternMemory
  pm = PatternMemory()
  pm.remember(session_id, query, plan, reasoning)
  similar = pm.recall(query)  → 找到最近的纹路
  continued = pm.continue_from(session_id, new_query) → 延续上一轮
"""

import time, hashlib, json, re, math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from collections import OrderedDict

BASE = Path(__file__).parent
MEMORY_FILE = BASE / "data" / "pattern_memory.json"
MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════════
# 纹路节点
# ════════════════════════════════════════════════════════

@dataclass
class PatternNode:
    """一个研究纹路 = 一次知纹分解的完整结构。"""

    id: str                             # 纹路ID
    query: str                          # 原始问题
    session_id: str = ""                # 对话会话ID
    timestamp: float = 0.0              # 创建时间

    # DAG结构
    sub_problems: list[str] = field(default_factory=list)    # 子问题列表
    dependencies: dict = field(default_factory=dict)          # 依赖关系
    execution_order: list[str] = field(default_factory=list)  # 执行顺序

    # 推理结构
    chain_count: int = 0                # 推理链数
    claim_count: int = 0                # 声明数
    inference_count: int = 0            # 推理步数
    confidence: float = 0.0             # 综合置信度

    # 证据摘要
    evidence_scores: dict = field(default_factory=dict)      # 子问题→评分
    keywords: list[str] = field(default_factory=list)        # 关键词
    domain: str = ""                    # 领域

    # 延续关系
    parent_id: str = ""                 # 父纹路ID (如果是追问)
    children_ids: list[str] = field(default_factory=list)    # 子纹路ID
    continuation_depth: int = 0         # 延续深度 (0=首问)


# ════════════════════════════════════════════════════════
# 纹路记忆引擎
# ════════════════════════════════════════════════════════

class PatternMemory:
    """纹路记忆 — 存·取·延续。"""

    MAX_PATTERNS = 200                  # 最多保存200个纹路
    MAX_CONTINUATION_DEPTH = 5          # 最多延续5层追问
    SIMILARITY_THRESHOLD = 0.35         # 相似度阈值

    def __init__(self):
        self.patterns: OrderedDict[str, PatternNode] = OrderedDict()
        self.session_patterns: dict[str, list[str]] = {}  # session_id → pattern_ids
        self._load()

    # ─── 存储 ───

    def remember(self, session_id: str, query: str,
                 plan=None, reasoning: dict = None,
                 parent_id: str = "") -> str:
        """
        记住一次研究的纹路。

        存下: DAG结构 + 推理链形状 + 证据评分 + 关键词
        """
        pattern_id = hashlib.sha256(
            (query + str(time.time())).encode()
        ).hexdigest()[:12]

        # 提取DAG结构
        sub_problems = []
        dependencies = {}
        execution_order = []
        evidence_scores = {}

        if plan:
            if hasattr(plan, 'sub_problems'):
                for qid, sp in plan.sub_problems.items():
                    sub_problems.append(sp.question if hasattr(sp, 'question') else str(sp))
                    if hasattr(sp, 'dependencies'):
                        dependencies[qid] = sp.dependencies
                    if hasattr(sp, 'evidence_score'):
                        evidence_scores[qid] = sp.evidence_score
            if hasattr(plan, 'execution_order'):
                execution_order = plan.execution_order

        # 提取推理结构
        chain_count = 0
        claim_count = 0
        inference_count = 0
        confidence = 0.0

        if reasoning:
            chain_count = len(reasoning.get("chains", []))
            claim_count = reasoning.get("claims_count", 0)
            inference_count = reasoning.get("inferences_count", 0)
            confidence = reasoning.get("confidence", 0.0)

        # 提取关键词
        keywords = self._extract_keywords(query)

        # 延续关系
        continuation_depth = 0
        if parent_id and parent_id in self.patterns:
            parent = self.patterns[parent_id]
            parent.children_ids.append(pattern_id)
            continuation_depth = parent.continuation_depth + 1

        pattern = PatternNode(
            id=pattern_id,
            query=query,
            session_id=session_id,
            timestamp=time.time(),
            sub_problems=sub_problems,
            dependencies=dependencies,
            execution_order=execution_order,
            chain_count=chain_count,
            claim_count=claim_count,
            inference_count=inference_count,
            confidence=confidence,
            evidence_scores=evidence_scores,
            keywords=keywords,
            domain=self._detect_domain(query),
            parent_id=parent_id,
            continuation_depth=continuation_depth,
        )

        # 存储
        self.patterns[pattern_id] = pattern

        # 会话索引
        if session_id not in self.session_patterns:
            self.session_patterns[session_id] = []
        self.session_patterns[session_id].append(pattern_id)

        # LRU淘汰
        while len(self.patterns) > self.MAX_PATTERNS:
            self.patterns.popitem(last=False)

        self._save()
        return pattern_id

    # ─── 检索 ───

    def recall(self, query: str, top_k: int = 3) -> list[dict]:
        """
        找到与查询最相似的纹路。

        返回: [{pattern_id, query, similarity, sub_problems, chain_count, confidence}]
        """
        query_keywords = set(self._extract_keywords(query))
        if not query_keywords:
            return []

        scored = []
        for pid, pattern in self.patterns.items():
            pattern_kw = set(pattern.keywords)
            if not pattern_kw:
                continue

            # Jaccard相似度
            intersection = query_keywords & pattern_kw
            union = query_keywords | pattern_kw
            sim = len(intersection) / max(len(union), 1)

            # 领域加成
            query_domain = self._detect_domain(query)
            if query_domain and query_domain == pattern.domain:
                sim *= 1.2

            if sim >= self.SIMILARITY_THRESHOLD:
                scored.append((sim, pattern))

        # 按相似度排序
        scored.sort(key=lambda x: -x[0])

        results = []
        for sim, pattern in scored[:top_k]:
            results.append({
                "pattern_id": pattern.id,
                "query": pattern.query[:120],
                "similarity": round(sim, 3),
                "sub_problems": pattern.sub_problems[:5],
                "chain_count": pattern.chain_count,
                "confidence": pattern.confidence,
                "timestamp": pattern.timestamp,
                "continuation_depth": pattern.continuation_depth,
            })

        return results

    def continue_from(self, session_id: str, new_query: str) -> Optional[dict]:
        """
        检测新查询是否延续当前会话的上一轮研究。

        如果是追问 → 返回父纹路信息，建议复用DAG结构。
        如果是全新问题 → 返回 None。
        """
        if session_id not in self.session_patterns:
            return None

        session_patterns = self.session_patterns.get(session_id, [])
        if not session_patterns:
            return None

        # 取最近的纹路
        last_pid = session_patterns[-1]
        last_pattern = self.patterns.get(last_pid)
        if not last_pattern:
            return None

        # 检测延续信号
        continuation_score = self._detect_continuation(last_pattern.query, new_query)

        if continuation_score < 0.3:
            return None

        # 延续深度检查
        if last_pattern.continuation_depth >= self.MAX_CONTINUATION_DEPTH:
            return {
                "continued": True,
                "warning": "已达最大追问深度%d" % self.MAX_CONTINUATION_DEPTH,
                "parent_id": last_pid,
                "depth": last_pattern.continuation_depth + 1,
            }

        return {
            "continued": True,
            "parent_id": last_pid,
            "parent_query": last_pattern.query[:120],
            "parent_dag": {
                "sub_problems": last_pattern.sub_problems,
                "execution_order": last_pattern.execution_order,
            },
            "continuation_score": round(continuation_score, 3),
            "depth": last_pattern.continuation_depth + 1,
        }

    # ─── 会话上下文 ───

    def get_session_context(self, session_id: str) -> dict:
        """获取当前会话的研究上下文。"""
        if session_id not in self.session_patterns:
            return {"has_history": False}

        patterns = self.session_patterns.get(session_id, [])
        recent = []
        for pid in patterns[-5:]:  # 最近5个纹路
            p = self.patterns.get(pid)
            if p:
                recent.append({
                    "query": p.query[:100],
                    "domain": p.domain,
                    "confidence": p.confidence,
                })

        return {
            "has_history": True,
            "total_patterns": len(patterns),
            "recent_patterns": recent,
            "latest_domain": recent[-1]["domain"] if recent else "",
        }

    # ─── 持久化 ───

    def _save(self):
        try:
            data = {
                "patterns": {
                    pid: {
                        "id": p.id,
                        "query": p.query,
                        "session_id": p.session_id,
                        "timestamp": p.timestamp,
                        "sub_problems": p.sub_problems,
                        "dependencies": p.dependencies,
                        "execution_order": p.execution_order,
                        "chain_count": p.chain_count,
                        "claim_count": p.claim_count,
                        "inference_count": p.inference_count,
                        "confidence": p.confidence,
                        "evidence_scores": p.evidence_scores,
                        "keywords": p.keywords,
                        "domain": p.domain,
                        "parent_id": p.parent_id,
                        "children_ids": p.children_ids,
                        "continuation_depth": p.continuation_depth,
                    }
                    for pid, p in list(self.patterns.items())[-100:]  # 只保留最近100个
                },
                "session_patterns": {
                    sid: pids[-10:]  # 每会话最多10个
                    for sid, pids in self.session_patterns.items()
                },
            }
            MEMORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception:
            pass

    def _load(self):
        try:
            if MEMORY_FILE.exists():
                data = json.loads(MEMORY_FILE.read_text())
                for pid, pd in data.get("patterns", {}).items():
                    pattern = PatternNode(
                        id=pd.get("id", pid),
                        query=pd.get("query", ""),
                        session_id=pd.get("session_id", ""),
                        timestamp=pd.get("timestamp", 0),
                        sub_problems=pd.get("sub_problems", []),
                        dependencies=pd.get("dependencies", {}),
                        execution_order=pd.get("execution_order", []),
                        chain_count=pd.get("chain_count", 0),
                        claim_count=pd.get("claim_count", 0),
                        inference_count=pd.get("inference_count", 0),
                        confidence=pd.get("confidence", 0),
                        evidence_scores=pd.get("evidence_scores", {}),
                        keywords=pd.get("keywords", []),
                        domain=pd.get("domain", ""),
                        parent_id=pd.get("parent_id", ""),
                        children_ids=pd.get("children_ids", []),
                        continuation_depth=pd.get("continuation_depth", 0),
                    )
                    self.patterns[pid] = pattern
                self.session_patterns = data.get("session_patterns", {})
        except Exception:
            self.patterns = OrderedDict()
            self.session_patterns = {}

    # ─── 辅助 ───

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词 (中文2-4字词组 + 英文词)。"""
        # 中文2-4字词组
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        # 英文词
        english_words = re.findall(r'[A-Za-z]{2,}', text)
        # 数字+单位
        numbers = re.findall(r'\d+\.?\d*[%％]?', text)

        keywords = chinese_words[:8] + english_words[:3] + numbers[:3]
        return list(set(keywords))[:15]

    def _detect_domain(self, text: str) -> str:
        """检测研究领域。"""
        domain_keywords = {
            "经济学": ["经济", "GDP", "通胀", "赤字", "货币", "财政", "MMT", "就业", "利率", "汇率", "通缩"],
            "物理学": ["物理", "量子", "力学", "能量", "熵", "热力学", "引力"],
            "历史学": ["历史", "朝代", "战争", "革命", "事件"],
            "计算机": ["算法", "编程", "代码", "AI", "机器学习", "深度学习", "神经网络"],
            "哲学": ["哲学", "存在", "意义", "伦理", "形而上学"],
            "社会学": ["社会", "人口", "教育", "制度", "文化", "老龄化"],
        }
        for domain, keywords in domain_keywords.items():
            if any(kw in text for kw in keywords):
                return domain
        return "通用"

    def _detect_continuation(self, prev_query: str, new_query: str) -> float:
        """检测新查询是否是上一轮的延续。"""
        # 关键词重叠
        prev_kw = set(self._extract_keywords(prev_query))
        new_kw = set(self._extract_keywords(new_query))

        if not prev_kw or not new_kw:
            return 0.0

        overlap = len(prev_kw & new_kw)
        jaccard = overlap / max(len(prev_kw | new_kw), 1)

        # 追问词加分
        continuation_signals = ["那", "那么", "接", "继续", "再", "也", "还",
                                "进一步", "深入", "具体", "比如", "例如"]
        signal_bonus = 0.0
        for sig in continuation_signals:
            if new_query.startswith(sig) or sig in new_query[:10]:
                signal_bonus = 0.3
                break

        # 指代词加分
        reference_signals = ["这个", "那个", "它", "这些", "上述", "前面"]
        ref_bonus = 0.0
        for ref in reference_signals:
            if ref in new_query:
                ref_bonus = 0.2
                break

        score = jaccard + signal_bonus + ref_bonus
        return min(score, 1.0)


# ════════════════════════════════════════════════════════
# 全局单例
# ════════════════════════════════════════════════════════

_memory: Optional[PatternMemory] = None


def get_memory() -> PatternMemory:
    global _memory
    if _memory is None:
        _memory = PatternMemory()
    return _memory
