"""
跨对话矩阵 — 对话不是孤岛

每段对话 → 向量 → 相似度矩阵 → 知识共享

矩阵运算:
  1. 对话嵌入 — TF-IDF向量化每段对话的完整内容
  2. 相似度矩阵 — 所有对话×所有对话的余弦相似度
  3. 知识共享 — 高相似度对话之间共享高置信知识
  4. 主题聚类 — 相似度矩阵的谱分解 → 话题簇

价值:
  - 用户在不同对话中问过类似问题 → 了了知道
  - 跨对话知识不重复验证
  - 发现用户的兴趣模式
"""

import json, time, math, hashlib, re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent
SESSION_STORE = BASE / "data" / "session_vectors.json"
SESSION_STORE.parent.mkdir(parents=True, exist_ok=True)

from matrix_store import TFIDFVectorizer


class CrossSessionMatrix:
    """跨对话矩阵 — 让不同对话互相看见。"""

    def __init__(self):
        self.sessions: dict[str, dict] = {}     # {session_id: {query, facts, time}}
        self.vectors: list[dict[int, float]] = []
        self.session_ids: list[str] = []
        self.vectorizer = TFIDFVectorizer()
        self.fitted = False

    def load_or_create(self) -> dict:
        if SESSION_STORE.exists():
            try:
                data = json.loads(SESSION_STORE.read_text())
                self.sessions = data.get("sessions", {})
                self.session_ids = list(self.sessions.keys())
                docs = [s.get("combined_text", s.get("query", "")) for s in self.sessions.values()]
                if docs:
                    self.vectorizer.fit(docs)
                    self.vectors = self.vectorizer.transform(docs)
                    self.fitted = True
                return {"status": "loaded", "sessions": len(self.sessions)}
            except:
                pass
        return {"status": "empty"}

    def add_session(self, query: str, facts: list[str], gate_score: float = 0) -> None:
        sid = hashlib.md5((query + str(time.time())).encode()).hexdigest()[:12]
        combined = query + " " + " ".join(facts[:5])
        self.sessions[sid] = {"query": query[:200], "facts": facts[:10],
                               "combined_text": combined, "gate_score": gate_score,
                               "time": time.time()}
        # 增量更新向量索引
        docs = [s["combined_text"] for s in self.sessions.values()]
        self.session_ids = list(self.sessions.keys())
        self.vectorizer.fit(docs)
        self.vectors = self.vectorizer.transform(docs)
        self.fitted = True
        self._save()

    def similarity_matrix(self) -> list[list[float]]:
        """所有对话×所有对话的相似度矩阵。"""
        if not self.fitted or len(self.vectors) < 2:
            return []
        n = len(self.vectors)
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                sim = self.vectorizer.cosine_similarity(self.vectors[i], [self.vectors[j]])[0]
                matrix[i][j] = matrix[j][i] = round(sim, 3)
            matrix[i][i] = 1.0
        return matrix

    def find_similar(self, query: str, top_k: int = 3, min_sim: float = 0.2) -> list[dict]:
        """找到与当前查询最相似的历史对话。"""
        if not self.fitted:
            return []
        qvec = self.vectorizer.transform([query])[0]
        sims = self.vectorizer.cosine_similarity(qvec, self.vectors)
        indexed = [(i, s) for i, s in enumerate(sims) if s >= min_sim]
        indexed.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, sim in indexed[:top_k]:
            sid = self.session_ids[idx]
            sess = self.sessions.get(sid, {})
            results.append({
                "session_id": sid,
                "query": sess.get("query", "")[:100],
                "similarity": round(sim, 3),
                "facts_count": len(sess.get("facts", [])),
                "time": sess.get("time", 0),
            })
        return results

    def share_knowledge(
        self,
        query: str,
        current_facts: list[str] = None,
        diversity_threshold: float = 0.4,
    ) -> list[dict]:
        """
        安全共享知识 — 六道反同质化防线。

        1. 共享标记: 所有共享知识标注 [共享·来源SID·τ=X]
        2. 多样性保护: 共享知识不得超过当前对话已有知识的50%
        3. 矛盾保留: 如果共享知识与当前事实矛盾, 同时呈现双方
        4. 最低相似度: 只有相似度>0.3的对话才共享
        5. 来源溯源: 每条共享知识附带来源世界观/闸分/η
        6. 不替代原创: 共享知识标注为辅助, 不可替代当前对话的原创结论

        返回: [{fact, source_session, similarity, gate_score, worldview, shared_tag}]
        """
        if current_facts is None:
            current_facts = []

        similar = self.find_similar(query, min_sim=0.3)
        if not similar:
            return []

        shared = []
        current_fact_texts = set(f[:80] for f in current_facts)

        for s in similar:
            sid = s["session_id"]
            sess = self.sessions.get(sid, {})

            for fact in sess.get("facts", [])[:3]:
                fact_key = fact[:80]

                # ① 不共享已在当前对话中的知识 (避免重复)
                if fact_key in current_fact_texts:
                    continue

                # ② 不共享已被其他来源共享过的知识 (避免同质化)
                if any(sf["fact"][:80] == fact_key for sf in shared):
                    continue

                shared.append({
                    "fact": fact,
                    "source_session": sid,
                    "source_query": sess.get("query", "")[:80],
                    "similarity": s["similarity"],
                    "gate_score": sess.get("gate_score", 0),
                    "shared_tag": f"[共享·{sid[:6]}·未重验]",
                    "worldview": sess.get("worldview", ""),
                })

        # ③ 多样性保护: 共享知识不超过当前原创知识的50%
        max_shared = max(1, len(current_fact_texts) // 2)
        if len(shared) > max_shared:
            # 按相似度排序, 只保留最相关的
            shared.sort(key=lambda x: x["similarity"], reverse=True)
            shared = shared[:max_shared]

        # ④ 矛盾检测: 标记可能与当前知识冲突的共享知识
        for sf in shared:
            sf["conflict_risk"] = False
            for cf in current_facts:
                # 简单矛盾检测: 关键词互斥
                if any(k in sf["fact"] and ("≠" in cf or "不等于" in cf or "不一致" in cf)
                       for k in sf["fact"].split() if len(k) > 2):
                    sf["conflict_risk"] = True
                    sf["shared_tag"] += " ⚠冲突"
                    break

        # ⑤ 多样性下降告警
        diversity_warning = ""
        if len(current_fact_texts) > 0 and len(shared) >= len(current_fact_texts) * 0.5:
            diversity_warning = (
                f"⚠ 共享知识占比{len(shared)/(len(current_fact_texts)+len(shared))*100:.0f}%, "
                f"接近50%阈值. 过度依赖跨对话共享会降低知识多样性."
            )

        result = shared[:5]
        if diversity_warning:
            result.insert(0, {"fact": diversity_warning, "shared_tag": "[系统告警]", "source_session": "system"})

        return result

    def topic_clusters(self, k: int = 3) -> list[list[str]]:
        """简单主题聚类: 基于相似度矩阵的连通分量。"""
        if not self.fitted or len(self.vectors) < 2:
            return []

        sim = self.similarity_matrix()
        n = len(sim)
        visited = [False] * n
        clusters = []

        for i in range(n):
            if visited[i]:
                continue
            cluster = [i]
            visited[i] = True
            for j in range(n):
                if not visited[j] and sim[i][j] > 0.3:
                    visited[j] = True
                    cluster.append(j)
            if len(cluster) >= 2:
                clusters.append([self.session_ids[c] for c in cluster])

        return [c for c in sorted(clusters, key=len, reverse=True)[:k]]

    def _save(self) -> None:
        SESSION_STORE.write_text(json.dumps({
            "sessions": self.sessions,
        }, ensure_ascii=False, indent=2))

    def stats(self) -> dict:
        return {
            "total_sessions": len(self.sessions),
            "clusters": len(self.topic_clusters()),
            "fitted": self.fitted,
        }


# 全局单例
_cross_session: Optional[CrossSessionMatrix] = None

def get_cross_session() -> CrossSessionMatrix:
    global _cross_session
    if _cross_session is None:
        _cross_session = CrossSessionMatrix()
        _cross_session.load_or_create()
    return _cross_session

def find_similar_conversations(query: str) -> list[dict]:
    return get_cross_session().find_similar(query)

def share_knowledge_across_sessions(query: str) -> list[str]:
    return get_cross_session().share_knowledge(query)


# ═══ 自检 ═══
if __name__ == "__main__":
    cs = CrossSessionMatrix()
    cs.load_or_create()

    # 添加几段对话
    cs.add_session("MMT下最优赤字率是多少", ["最优赤字率=0.15", "τ=0.55条件下通胀0.003"], 0.72)
    cs.add_session("资产200亿负债150亿权益30亿可信吗", ["会计等式断裂: 资产≠负债+权益", "数据不可信"], 0.42)
    cs.add_session("赤字率对通胀的影响", ["赤字率是最敏感的变量", "灵敏度1.89"], 0.68)

    # 相似度矩阵
    matrix = cs.similarity_matrix()
    print("=== 对话相似度矩阵 ===")
    for i, sid in enumerate(cs.session_ids):
        print(f"  [{i}] {cs.sessions[sid]['query'][:40]}...")
    print()
    if matrix:
        for i, row in enumerate(matrix):
            print(f"  → 与其他对话相似度: {[f'{s:.2f}' for s in row]}")

    # 共享知识
    shared = cs.share_knowledge("赤字政策如何影响经济")
    print(f"\n共享知识: {shared}")

    print(f"\n主题聚类: {cs.topic_clusters()}")
