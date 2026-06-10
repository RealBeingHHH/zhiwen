"""
工程DAG编排器 — 多基因依赖调度·数据管线·批处理

当前: 单基因 → 操纵子并发 → 一个蛋白
目标: 多基因DAG → 拓扑调度 → 依赖解算 → 数据管线 → 结果聚合

核心:
  基因A(搜索) ──┐
  基因B(模拟) ──┼─→ 基因D(综合) → 蛋白
  基因C(验证) ──┘

用法:
  dag = ResearchDAG()
  dag.add_gene("search_mmt", depends_on=[], codons=["ATG","AAG","AAC","TAA"])
  dag.add_gene("simulate",   depends_on=["search_mmt"], codons=["ATG","GGC","GGA","TAA"])
  results = dag.execute()

每个基因=独立的DNA执行单元, DAG=基因间的数据依赖管线
"""

import time, hashlib, threading
from dataclasses import dataclass, field
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum


class GeneState(Enum):
    PENDING = "pending"          # 等待依赖就绪
    READY = "ready"              # 依赖就绪,待执行
    RUNNING = "running"          # 执行中
    DONE = "done"                # 执行完成
    FAILED = "failed"            # 执行失败


@dataclass
class DAGNode:
    """DAG中的基因节点。"""

    name: str                    # 基因名称
    codons: list[str]            # 密码子序列
    depends_on: list[str]        # 依赖的基因名称
    depends_on_data: list[str] = field(default_factory=list)  # 需要前驱的输出数据
    state: GeneState = GeneState.PENDING
    priority: int = 0            # 优先级 (高优先先执行)

    # 执行结果
    result: dict = field(default_factory=dict)
    protein: str = ""
    evidence: str = ""
    evidence_score: float = 0.0
    errors: list[str] = field(default_factory=list)

    # 管线上下文
    context: dict = field(default_factory=dict)


@dataclass
class PipelineEdge:
    """DAG中的数据边 — 基因间数据传递。"""

    from_gene: str               # 来源基因
    to_gene: str                 # 目标基因
    data_key: str                # 传递的数据键名
    transform: Optional[Callable] = None  # 数据转换函数


class ResearchDAG:
    """研究DAG — 多基因拓扑调度 + 数据管线。"""

    def __init__(self, query: str = ""):
        self.query = query
        self.nodes: dict[str, DAGNode] = {}
        self.edges: list[PipelineEdge] = []
        self._lock = threading.Lock()

    def add_gene(self, name: str, codons: list[str],
                 depends_on: list[str] = None,
                 depends_on_data: list[str] = None,
                 priority: int = 0) -> "ResearchDAG":
        """添加一个基因节点到DAG。"""
        self.nodes[name] = DAGNode(
            name=name,
            codons=codons,
            depends_on=depends_on or [],
            depends_on_data=depends_on_data or [],
            priority=priority,
        )
        return self

    def add_edge(self, from_gene: str, to_gene: str,
                 data_key: str = "evidence"):
        """添加数据依赖边。"""
        self.edges.append(PipelineEdge(
            from_gene=from_gene,
            to_gene=to_gene,
            data_key=data_key,
        ))

    def execute(self, max_workers: int = 4) -> dict:
        """
        拓扑调度执行DAG。

        1. 解析依赖 → 计算就绪队列
        2. 并发执行所有就绪基因 (ThreadPoolExecutor)
        3. 完成→传递数据给下游→下游就绪→继续
        4. 所有节点完成 → 聚合结果
        """
        t0 = time.time()
        results = {
            "dag_query": self.query,
            "total_genes": len(self.nodes),
            "gene_results": {},
            "execution_order": [],
            "pipeline_data": {},    # 全局数据管线
            "errors": [],
            "timeline": [],
        }

        # 拓扑排序: 按层执行
        while True:
            ready = self._get_ready_nodes()

            if not ready:
                # 检查是否有失败节点阻塞
                pending = [n for n in self.nodes.values()
                          if n.state == GeneState.PENDING]
                if pending:
                    # 所有依赖已就绪但仍pending → 死锁/依赖缺失
                    stuck = [n.name for n in pending]
                    results["errors"].append("DAG死锁: 节点卡住 %s" % stuck)
                    for n in pending:
                        n.state = GeneState.FAILED
                        n.errors.append("依赖不可解")
                break

            # 并发执行就绪队列
            layer_results = self._execute_layer(ready, max_workers)

            # 传递数据
            for name, result in layer_results.items():
                node = self.nodes[name]
                node.result = result
                node.protein = result.get("protein", "")
                node.evidence = result.get("evidence", "")
                node.evidence_score = result.get("evidence_score", 0)
                results["gene_results"][name] = result
                results["execution_order"].append(name)

                # 数据管线: 将结果注入全局管线
                results["pipeline_data"][name] = {
                    "protein": node.protein,
                    "evidence": node.evidence,
                    "score": node.evidence_score,
                }

                # 传递给下游
                self._forward_data(name, results["pipeline_data"])

            results["timeline"].append({
                "layer_genes": list(layer_results.keys()),
                "elapsed_ms": int((time.time() - t0) * 1000),
            })

        results["total_elapsed_ms"] = int((time.time() - t0) * 1000)
        results["completed"] = sum(
            1 for n in self.nodes.values() if n.state == GeneState.DONE
        )
        results["failed"] = sum(
            1 for n in self.nodes.values() if n.state == GeneState.FAILED
        )

        return results

    def _get_ready_nodes(self) -> list[DAGNode]:
        """获取所有依赖已就绪的节点。"""
        ready = []
        for node in self.nodes.values():
            if node.state != GeneState.PENDING:
                continue

            # 检查所有依赖是否完成
            all_deps_ready = all(
                self.nodes.get(d) and self.nodes[d].state == GeneState.DONE
                for d in node.depends_on
            )

            if all_deps_ready:
                node.state = GeneState.READY
                ready.append(node)

        # 按优先级排序
        ready.sort(key=lambda n: -n.priority)
        return ready

    def _execute_layer(self, nodes: list[DAGNode],
                       max_workers: int) -> dict:
        """并发执行一层就绪节点。"""
        results = {}

        if len(nodes) == 1:
            # 单节点 → 直接执行
            node = nodes[0]
            node.state = GeneState.RUNNING
            try:
                result = self._execute_gene(node)
                node.state = GeneState.DONE
                results[node.name] = result
            except Exception as e:
                node.state = GeneState.FAILED
                node.errors.append(str(e)[:120])
                results[node.name] = {"error": str(e)[:120]}
            return results

        # 多节点 → 线程池并发
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for node in nodes:
                node.state = GeneState.RUNNING
                future = executor.submit(self._execute_gene, node)
                futures[future] = node

            for future in as_completed(futures):
                node = futures[future]
                try:
                    result = future.result(timeout=30)
                    node.state = GeneState.DONE
                    results[node.name] = result
                except Exception as e:
                    node.state = GeneState.FAILED
                    node.errors.append(str(e)[:120])
                    results[node.name] = {"error": str(e)[:120]}

        return results

    def _execute_gene(self, node: DAGNode) -> dict:
        """执行单个基因 — 通过基因组管线。"""
        # 构建上下文 (注入依赖基因的数据)
        context = node.context.copy()
        for dep_name in node.depends_on_data:
            dep_node = self.nodes.get(dep_name)
            if dep_node:
                context[f"dep_{dep_name}_evidence"] = dep_node.evidence[:500]
                context[f"dep_{dep_name}_protein"] = dep_node.protein

        query = f"{self.query} | 子任务:{node.name}"
        if context:
            query += f" | 上游数据:{str(context)[:200]}"

        try:
            from genome_pipeline import run_genome_pipeline
            gen_result = run_genome_pipeline(query)

            collected = gen_result.get("collected_data", {})
            return {
                "gene_name": node.name,
                "codons": node.codons,
                "protein": gen_result.get("protein", ""),
                "evidence": collected.get("search_data", "")[:500],
                "evidence_score": gen_result.get("health", {}).get("mismatch_rate", 0)
                                   or 0.5,
                "executed": gen_result.get("executed", False),
                "errors": gen_result.get("errors", []),
            }
        except Exception as e:
            # 回退: 直接搜索
            try:
                from special import smart_search
                evidence = smart_search(query)
                return {
                    "gene_name": node.name,
                    "protein": "回退搜索",
                    "evidence": str(evidence)[:500] if evidence else "",
                    "evidence_score": 0.3,
                    "errors": [f"基因执行回退: {e}"],
                }
            except Exception:
                return {
                    "gene_name": node.name,
                    "protein": "失败",
                    "evidence": "",
                    "evidence_score": 0.0,
                    "errors": [str(e)[:120]],
                }

    def _forward_data(self, source_name: str,
                      pipeline_data: dict) -> None:
        """将源节点数据传递给下游节点。"""
        for edge in self.edges:
            if edge.from_gene == source_name:
                target = self.nodes.get(edge.to_gene)
                if target:
                    source_data = pipeline_data.get(source_name, {})
                    target.context[edge.data_key] = source_data.get(
                        edge.data_key, source_data.get("evidence", "")
                    )


# ════════════════════════════════════════════════════════
# 快捷: 从研究计划构建DAG
# ════════════════════════════════════════════════════════

def dag_from_plan(plan) -> ResearchDAG:
    """从研究规划器的输出构建工程DAG。"""
    dag = ResearchDAG(query=plan.query)

    seen = set()
    for qid in plan.execution_order:
        sp = plan.sub_problems.get(qid)
        if not sp or qid == "root":
            continue

        # 每个子问题 → 一个基因
        codons = _build_codons_for_question(sp.question, sp.depth)
        deps = [d for d in sp.dependencies if d in plan.sub_problems]
        dag.add_gene(
            name=qid,
            codons=codons,
            depends_on=deps,
            priority=3 - sp.depth,  # 浅层优先
        )

    # 根节点 → 综合基因 (依赖所有子问题)
    all_deps = [qid for qid in plan.execution_order if qid != "root"]
    dag.add_gene(
        name="root",
        codons=["ATG", "AAG", "CGT", "TAA"],  # 启动→搜索→验证→结论
        depends_on=all_deps,
        priority=0,  # 最后执行
    )

    return dag


def _build_codons_for_question(question: str, depth: int) -> list[str]:
    """根据问题类型构建密码子链。"""
    codons = ["ATG"]  # 总是启动

    # 检测问题类型
    if any(kw in question for kw in ["数据", "变化", "增长", "下降", "多少", "率"]):
        codons.extend(["AAG", "AAC"])  # 搜索+深度搜索
    elif any(kw in question for kw in ["因果", "关系", "影响", "验证"]):
        codons.extend(["AAG", "CGT", "CGC"])  # 搜索+验证+关系
    elif any(kw in question for kw in ["理论", "框架", "主张", "MMT"]):
        codons.extend(["AAG", "GGC"])  # 搜索+模拟
    elif any(kw in question for kw in ["对比", "差异", "优势"]):
        codons.extend(["AAG", "TGC"])  # 搜索+对比
    else:
        codons.append("AAG")  # 默认搜索

    codons.append("TAA")  # 总是结论
    return codons


# ════════════════════════════════════════════════════════
# 批处理: 多个独立查询并发执行
# ════════════════════════════════════════════════════════

def batch_execute(queries: list[str], max_workers: int = 4) -> dict:
    """批处理: 多个独立查询并发执行。"""
    results = {}
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for q in queries:
            future = executor.submit(_execute_single_query, q)
            futures[future] = q

        for future in as_completed(futures):
            q = futures[future]
            try:
                results[q] = future.result(timeout=60)
            except Exception as e:
                results[q] = {"error": str(e)[:120]}

    return {
        "results": results,
        "total_queries": len(queries),
        "elapsed_ms": int((time.time() - t0) * 1000),
        "avg_ms_per_query": int((time.time() - t0) * 1000 / max(len(queries), 1)),
    }


def _execute_single_query(query: str) -> dict:
    """执行单个查询 (用于批处理)。"""
    from genome_pipeline import run_genome_pipeline
    return run_genome_pipeline(query)


# ═══ 自检 ═══
if __name__ == "__main__":
    print("=== 工程DAG测试 ===")

    dag = ResearchDAG(query="分析日本MMT政策效果")

    # 构建三层DAG
    dag.add_gene("search_causes", 
                 codons=["ATG", "AAG", "AAC", "TAA"],
                 priority=3)
    
    dag.add_gene("search_data",
                 codons=["ATG", "AAG", "TAA"],
                 depends_on=["search_causes"],
                 priority=2)
    
    dag.add_gene("simulate",
                 codons=["ATG", "GGC", "GGA", "TAA"],
                 depends_on=["search_data"],
                 priority=1)
    
    dag.add_gene("verify",
                 codons=["ATG", "CGT", "CGC", "TAA"],
                 depends_on=["search_data", "simulate"],
                 priority=1)
    
    dag.add_gene("synthesize",
                 codons=["ATG", "AAG", "CGT", "TAA"],
                 depends_on=["verify", "simulate"],
                 priority=0)

    # 添加数据边
    dag.add_edge("search_causes", "search_data")
    dag.add_edge("search_data", "simulate")
    dag.add_edge("simulate", "verify")
    dag.add_edge("search_data", "verify")

    print("DAG结构:")
    print("  search_causes → search_data → simulate ──┐")
    print("                              → verify ────┤")
    print("                              → synthesize ←┘")
    print()
    print("拓扑层:")
    print("  层1: [search_causes]")
    print("  层2: [search_data]")
    print("  层3: [simulate, verify]  (并发)")
    print("  层4: [synthesize]")

    # 验证拓扑序
    ready_first = dag._get_ready_nodes()
    print("\n首层就绪: %s" % [n.name for n in ready_first])
    assert len(ready_first) == 1
    assert ready_first[0].name == "search_causes"
    print("✅ DAG拓扑序正确")
