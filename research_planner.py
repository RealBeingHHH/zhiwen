# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Copyright (c) 2026 知纹 (Zhiwen) Project

"""
研究规划器 — 模糊问题 → 子问题DAG → 证据链闭合

三层能力共同起点:
  研究能力: 问题分解 + 子问题DAG + 证据链
  推理能力: 证据链 → 结构化输入 (供推理引擎消费)
  工程能力: 子问题 → 基因 → 密码子 → 并发执行 (DNA原生)

核心流程:
  1. 分解: query → LLM分析 → 子问题DAG (可验证的原子问题)
  2. 调度: 按拓扑序, 无依赖节点先执行, 依赖就绪后触发上游
  3. 执行: 每个子问题 → Genome基因 → 密码子链 → 操纵子并发
  4. 闭合: 子问题完成 → 标记evidence_closed → 依赖解算 → 上游推进

LLM监控铁律:
  所有LLM调用必须经过 voyager_llm.safe_llm_call
  每调用记录: φ-drift分数 · τ锚定状态 · 输入hash · 输出验证
  检测到φ-drift → 标记子问题"幻觉风险"
  τ锚定失败 → 数值声明标记"未锚定"

用法:
  from research_planner import ResearchPlanner
  planner = ResearchPlanner()
  plan = planner.decompose("MMT如何解决日本通缩？")
  results = planner.execute(plan)  # DAG拓扑执行
"""

import time, hashlib, json, re as _re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ════════════════════════════════════════════════════════
# 子问题节点
# ════════════════════════════════════════════════════════

@dataclass
class SubProblem:
    """DAG中的一个节点 = 一个可验证的原子研究问题。"""

    id: str                              # 唯一标识 (hash)
    question: str                        # 子问题文本
    depth: int = 0                       # DAG深度 (根=0)
    dependencies: list[str] = field(default_factory=list)  # 依赖的子问题ID
    dependents: list[str] = field(default_factory=list)    # 被谁依赖

    # 证据状态
    evidence_state: str = "pending"      # pending→searching→collected→verified→closed
    evidence_text: str = ""              # 收集到的证据
    evidence_score: float = 0.0          # 证据质量分 0-1
    gate_result: dict = field(default_factory=dict)  # 闸门结果

    # 基因执行
    gene_id: str = ""                    # 对应基因ID
    protein: str = ""                    # 表达蛋白
    execution_log: list = field(default_factory=list)

    # LLM监控
    llm_calls: list = field(default_factory=list)      # 所有LLM调用记录
    phi_drift_score: float = 0.0        # φ偏移分数 (0=正常)
    tau_anchored: bool = True           # τ锚定状态
    hallucination_risk: bool = False    # 幻觉风险标记

    # 结论
    conclusion: str = ""
    closed: bool = False


@dataclass
class ResearchPlan:
    """完整的研究规划 = 子问题DAG + 执行策略。"""

    query: str                           # 原始问题
    plan_id: str                         # 规划ID
    sub_problems: dict[str, SubProblem]  # id → SubProblem
    root_id: str                         # 根节点ID
    execution_order: list[str]           # 拓扑排序后的执行顺序
    meta: dict = field(default_factory=dict)  # 元信息(领域/方法推荐等)


# ════════════════════════════════════════════════════════
# LLM监控器
# ════════════════════════════════════════════════════════

class LLMMonitor:
    """所有LLM调用必须经过此监控器。"""

    _call_log: list = []

    @classmethod
    def log_call(cls, purpose: str, input_hash: str, output: str,
                 phi_drift: float, tau_anchored: bool) -> dict:
        """记录一次LLM调用。"""
        entry = {
            "timestamp": time.time(),
            "purpose": purpose,
            "input_hash": input_hash,
            "output_preview": output[:200] if output else "",
            "phi_drift": phi_drift,
            "tau_anchored": tau_anchored,
            "hallucination_flag": phi_drift > 0.3 or not tau_anchored,
        }
        cls._call_log.append(entry)
        return entry

    @classmethod
    def get_session_log(cls, since: float = 0) -> list:
        return [e for e in cls._call_log if e["timestamp"] >= since]

    @classmethod
    def hallucination_rate(cls) -> float:
        if not cls._call_log:
            return 0.0
        flagged = sum(1 for e in cls._call_log if e["hallucination_flag"])
        return flagged / len(cls._call_log)


# ════════════════════════════════════════════════════════
# 研究规划器
# ════════════════════════════════════════════════════════

class ResearchPlanner:
    """研究规划器 — 问题分解 + DAG调度 + 证据闭合。"""

    MAX_SUB_PROBLEMS = 8    # 最多分解为8个子问题
    MAX_DEPTH = 3           # 最大DAG深度

    def decompose(self, query: str) -> ResearchPlan:
        """
        将复杂研究问题分解为子问题DAG。

        使用LLM分析问题结构 → 识别独立维度 → 构建DAG。
        返回完整研究计划。
        """
        plan_id = hashlib.sha256((query + str(time.time())).encode()).hexdigest()[:12]
        sub_problems: dict[str, SubProblem] = {}

        # ═══ 步骤1: LLM分解 (受监控) ═══
        decomposition = self._llm_decompose(query)

        if not decomposition or len(decomposition.get("sub_questions", [])) < 2:
            # 无法分解 → 单节点DAG (整个问题作为一个基因)
            root = SubProblem(
                id="root",
                question=query,
                depth=0,
            )
            sub_problems["root"] = root
            return ResearchPlan(
                query=query, plan_id=plan_id,
                sub_problems=sub_problems, root_id="root",
                execution_order=["root"],
                meta={"decomposed": False, "reason": "原子问题无需分解"},
            )

        # ═══ 步骤2: 构建DAG节点 ═══
        sub_questions = decomposition.get("sub_questions", [])
        dependencies = decomposition.get("dependencies", {})
        meta = decomposition.get("meta", {})

        for sq in sub_questions[:self.MAX_SUB_PROBLEMS]:
            qid = hashlib.sha256(sq.encode()).hexdigest()[:8]
            deps = dependencies.get(qid, dependencies.get(sq[:30], []))
            sp = SubProblem(
                id=qid,
                question=sq,
                depth=1,  # 第一层子问题 (后续可递归深度)
                dependencies=deps,
            )
            sub_problems[qid] = sp

        # ═══ 步骤3: 创建根节点 (综合节点) ═══
        root = SubProblem(
            id="root",
            question=query,
            depth=0,
            dependencies=[],  # 根节点依赖所有子问题
        )
        # 根节点等待所有子问题完成
        for qid in sub_problems:
            root.dependencies.append(qid)
            sub_problems[qid].dependents.append("root")

        sub_problems["root"] = root

        # ═══ 步骤4: 拓扑排序 ═══
        order = self._topological_order(sub_problems)
        # 根节点放最后
        if "root" in order:
            order.remove("root")
            order.append("root")

        return ResearchPlan(
            query=query, plan_id=plan_id,
            sub_problems=sub_problems, root_id="root",
            execution_order=order,
            meta=meta,
        )

    def execute(self, plan: ResearchPlan) -> dict:
        """
        按拓扑序执行研究计划。

        每个子问题:
          1. 转录为基因 → 生成密码子链
          2. 操纵子并发执行 → 收集证据
          3. 过闸验证 → 标记evidence_state
          4. 依赖就绪 → 上游节点推进
        """
        results = {
            "plan_id": plan.plan_id,
            "query": plan.query,
            "sub_results": {},
            "root_conclusion": "",
            "llm_monitor": {},
            "execution_time_ms": 0,
        }

        t0 = time.time()

        # 按拓扑序执行
        for qid in plan.execution_order:
            sp = plan.sub_problems.get(qid)
            if not sp:
                continue

            # 检查依赖是否全部闭合
            if not self._dependencies_ready(sp, plan.sub_problems):
                continue

            # 执行子问题研究
            sub_result = self._execute_sub_problem(sp, plan)
            results["sub_results"][qid] = sub_result

            # 证据闭合
            if sub_result.get("evidence_score", 0) >= 0.5:
                sp.evidence_state = "closed"
                sp.closed = True

        # 根节点综合
        root = plan.sub_problems.get("root")
        if root:
            root_synthesis = self._synthesize(plan)
            results["root_conclusion"] = root_synthesis

        results["execution_time_ms"] = int((time.time() - t0) * 1000)
        results["llm_monitor"] = {
            "total_calls": len(LLMMonitor._call_log),
            "hallucination_rate": LLMMonitor.hallucination_rate(),
            "session_log": LLMMonitor.get_session_log(since=t0),
        }

        return results

    # ─── LLM分解 (受监控) ───

    def _llm_decompose(self, query: str) -> dict:
        """用LLM将问题分解为子问题DAG。所有调用受监控。"""
        try:
            from voyager_llm import safe_llm_call as _llm

            system = (
                "你是研究规划专家。将复杂问题分解为可独立验证的原子子问题。\n"
                "规则:\n"
                "1. 每个子问题必须可独立搜索/验证(不需要依赖其他子问题即可回答)\n"
                "2. 子问题之间标注依赖关系(如果B的答案依赖A)\n"
                "3. 最多分解为5个子问题\n"
                "4. 识别问题领域(经济学/物理学/历史等)和推荐研究方法\n"
                "5. 返回JSON格式,不要markdown包装\n"
                "格式: {\"sub_questions\":[\"子问题1\",...],"
                "\"dependencies\":{\"子问题1\":[],\"子问题2\":[\"子问题1\"]},"
                "\"meta\":{\"domain\":\"领域\",\"method\":\"推荐方法\"}}"
            )

            user = f"分解以下研究问题:\n{query}"

            result = _llm(system, user, max_tokens=800)

            # LLM监控记录
            input_hash = hashlib.sha256((system + user).encode()).hexdigest()[:12]
            phi_drift = self._detect_phi_drift(result)
            tau_anchored = self._check_tau_anchoring(result, query)

            LLMMonitor.log_call(
                purpose="问题分解",
                input_hash=input_hash,
                output=result,
                phi_drift=phi_drift,
                tau_anchored=tau_anchored,
            )

            # 解析JSON
            return self._parse_json_safe(result)

        except Exception as e:
            return {"sub_questions": [], "error": str(e)[:100]}

    # ─── 子问题执行 ───

    def _execute_sub_problem(self, sp: SubProblem, plan: ResearchPlan) -> dict:
        """执行单个子问题: 转录→基因→密码子→执行→闸门→证据。"""
        result = {
            "question": sp.question,
            "evidence_state": "searching",
            "evidence_text": "",
            "evidence_score": 0.0,
            "gene_id": "",
            "protein": "",
            "errors": [],
        }

        try:
            # 尝试通过基因组管线执行
            from genome_pipeline import run_genome_pipeline
            gen_result = run_genome_pipeline(sp.question)

            sp.gene_id = gen_result.get("gene_id", "")
            sp.protein = gen_result.get("protein", "")
            sp.execution_log = gen_result.get("execution_log", [])

            # 证据收集
            collected = gen_result.get("collected_data", {})
            evidence = collected.get("search_data", "")
            sp.evidence_text = evidence
            sp.evidence_state = "collected" if evidence else "searching"

            # 闸门评分
            gate = gen_result.get("gate_result") if "gate_result" in dir() else None
            if gate and hasattr(gate, 'overall_score'):
                sp.evidence_score = gate.overall_score
                sp.evidence_state = "verified" if gate.overall_score >= 0.5 else "collected"

            result.update({
                "evidence_state": sp.evidence_state,
                "evidence_text": evidence[:500] if evidence else "",
                "evidence_score": sp.evidence_score,
                "gene_id": sp.gene_id,
                "protein": sp.protein,
            })

        except Exception as e:
            result["errors"].append(str(e)[:120])
            # 回退: 直接搜索
            try:
                from special import smart_search
                evidence = smart_search(sp.question)
                if evidence:
                    sp.evidence_text = str(evidence)
                    sp.evidence_state = "collected"
                    sp.evidence_score = 0.4  # 未过闸, 默认低分
                    result["evidence_text"] = str(evidence)[:500]
                    result["evidence_state"] = "collected"
            except Exception:
                pass

        return result

    # ─── 综合 ───

    def _synthesize(self, plan: ResearchPlan) -> str:
        """收集所有子问题证据，综合为最终结论。受监控。"""
        try:
            from voyager_llm import safe_llm_call as _llm

            # 收集所有子问题证据
            evidence_parts = []
            for qid, sp in plan.sub_problems.items():
                if qid == "root":
                    continue
                if sp.evidence_text:
                    evidence_parts.append(
                        f"[子问题] {sp.question}\n"
                        f"[证据评分] {sp.evidence_score:.2f}\n"
                        f"[证据] {sp.evidence_text[:300]}\n"
                    )

            if not evidence_parts:
                return "(无子问题证据可综合)"

            system = (
                "你是研究综合专家。基于子问题证据,综合回答原始问题。\n"
                "规则:\n"
                "1. 每个结论标注证据来源(来自哪个子问题)\n"
                "2. 区分\"有证据支持\"和\"推测\"\n"
                "3. 指出证据缺口\n"
                "4. 数值声明标注是否为τ锚定"
            )

            user = (
                f"原始问题: {plan.query}\n\n"
                f"子问题证据:\n" + "\n---\n".join(evidence_parts)
            )

            result = _llm(system, user, max_tokens=1000)

            # 监控
            input_hash = hashlib.sha256((system + user).encode()).hexdigest()[:12]
            phi_drift = self._detect_phi_drift(result)
            tau_anchored = self._check_tau_anchoring(result, plan.query)

            LLMMonitor.log_call(
                purpose="证据综合",
                input_hash=input_hash,
                output=result,
                phi_drift=phi_drift,
                tau_anchored=tau_anchored,
            )

            return result

        except Exception as e:
            return f"(综合失败: {e})"

    # ─── DAG工具 ───

    def _topological_order(self, sub_problems: dict[str, SubProblem]) -> list[str]:
        """拓扑排序。叶节点(无依赖)先执行,根节点最后。"""
        visited = set()
        order = []

        def visit(qid):
            if qid in visited:
                return
            visited.add(qid)
            sp = sub_problems.get(qid)
            if sp:
                for dep in sp.dependencies:
                    if dep in sub_problems:
                        visit(dep)
            order.append(qid)

        for qid in sub_problems:
            visit(qid)

        return order

    def _dependencies_ready(self, sp: SubProblem,
                            sub_problems: dict[str, SubProblem]) -> bool:
        """检查所有依赖是否已闭合。"""
        for dep_id in sp.dependencies:
            dep = sub_problems.get(dep_id)
            if dep and not dep.closed:
                return False
        return True

    # ─── LLM监控辅助 ───

    def _detect_phi_drift(self, text: str) -> float:
        """检测φ漂移: 检查LLM输出中是否引入了无源数字。"""
        if not text:
            return 0.0
        # 简单启发式: 提取所有数字,检查是否有不合理数值
        import re
        numbers = re.findall(r'\b\d+\.?\d*\b', str(text))
        if not numbers:
            return 0.0
        # 太多数字 → 可能幻觉
        drift = min(len(numbers) / 20.0, 1.0)
        # 检查极端数值
        for n in numbers:
            try:
                v = float(n)
                if abs(v) > 1e12 or (0 < abs(v) < 1e-6):
                    drift += 0.1
            except:
                pass
        return min(drift, 1.0)

    def _check_tau_anchoring(self, text: str, query: str) -> bool:
        """检查τ锚定: 输出数字是否在输入中有锚。"""
        if not text or not query:
            return True
        import re
        out_nums = set(re.findall(r'\b\d+\.?\d*\b', str(text)))
        in_nums = set(re.findall(r'\b\d+\.?\d*\b', str(query)))
        # 如果输出数字不在输入中 → 未锚定
        unanchored = out_nums - in_nums
        if len(unanchored) > 3:
            return False
        return True

    def _parse_json_safe(self, text: str) -> dict:
        """安全解析LLM输出的JSON。"""
        try:
            # 尝试提取JSON块
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start:end+1])
        except:
            pass
        return {"sub_questions": [], "parse_error": True}


# ════════════════════════════════════════════════════════
# 快捷接口
# ════════════════════════════════════════════════════════

def plan_and_execute(query: str) -> dict:
    """一步: 规划 + 执行研究。"""
    planner = ResearchPlanner()
    plan = planner.decompose(query)
    return planner.execute(plan)


# ═══ 自检 ═══
if __name__ == "__main__":
    planner = ResearchPlanner()

    # 测试分解
    plan = planner.decompose("日本1990-2020年MMT政策效果如何？赤字率和通胀率的关系是什么？")
    print("研究计划: %s" % plan.plan_id)
    print("子问题数: %d" % len(plan.sub_problems))
    print("执行顺序: %s" % plan.execution_order)

    for qid in plan.execution_order:
        sp = plan.sub_problems[qid]
        deps = ",".join(sp.dependencies) if sp.dependencies else "无"
        print("  [%s] %s (深度%d, 依赖:%s)" % (qid, sp.question[:60], sp.depth, deps))

    print("\nLLM监控: %d次调用, 幻觉率%.0f%%" % (
        len(LLMMonitor._call_log),
        LLMMonitor.hallucination_rate() * 100
    ))
