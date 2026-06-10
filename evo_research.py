"""
织星研究引擎 · 第二阶段 — 演化群落
GenePool · ResearchAgent · DemocraticVote · Evolution · CarnotBudget

用法:
  from evo_research import evo_deep_research
  result = evo_deep_research("比亚迪和特斯拉对比")
"""

import concurrent.futures
import hashlib
import json
import math
import os
import random
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ═══ 路径 ═══
BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
GENE_POOL_FILE = DATA_DIR / "gene_pool.json"
EVOLUTION_LOG = DATA_DIR / "evolution_log.json"
MISMATCH_FILE = DATA_DIR / "mismatch_repository.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ═══ 专家团队 (从织星 expert_panel) ═══
EXPERT_TEAMS = {
    "投资委员会": {"weight": 15, "domain": "决策", "prompt": "综合所有分析给出最终评分"},
    "技术分析部": {"weight": 8, "domain": "技术面", "prompt": "从K线/均线/缠论角度分析"},
    "基本面研究部": {"weight": 8, "domain": "基本面", "prompt": "从财报/估值角度评估"},
    "宏观策略部": {"weight": 7, "domain": "宏观", "prompt": "从货币政策/经济周期评估"},
    "量化研究部": {"weight": 7, "domain": "量化", "prompt": "从因子模型/统计套利评分"},
    "风险管理部": {"weight": 6, "domain": "风控", "prompt": "从VaR/压力测试评估"},
    "行业制造组": {"weight": 5, "domain": "行业", "prompt": "从汽车/机械景气度评估"},
    "行业科技组": {"weight": 5, "domain": "行业", "prompt": "从TMT/半导体景气度评估"},
    "市场情报组": {"weight": 3, "domain": "情报", "prompt": "从竞品动态/趋势评估"},
    "法律合规组": {"weight": 3, "domain": "合规", "prompt": "从法规合规/信披评估"},
}


# ════════════════════════════════════════════════════════
#  GenePool — Agent 种群管理
# ════════════════════════════════════════════════════════

@dataclass
class ResearchAgent:
    """一个研究Agent。"""
    agent_id: str
    team: str                # 所属专家部门
    domain: str              # 领域
    prompt: str              # 分析视角
    weight: int              # 投票权重
    state: str = "active"    # active | hibernating | eliminated
    G_score: float = 5.0     # 梯度分 0-10
    success_count: int = 0   # 成功研究次数
    fail_count: int = 0      # 失败次数
    born_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    generation: int = 0      # 代数
    specialization: str = "" # 专长领域（演化积累）


class GenePool:
    """Agent基因池：管理研究Agent的整个生命周期。"""

    MAX_HIBERNATE = 30
    MAX_ACTIVE = 15
    ELIMINATE_THRESHOLD = 2.0  # G<2 持续N轮 → 淘汰
    HIBERNATE_IDLE = 300       # 300秒无任务 → 休眠

    def __init__(self):
        self.agents: dict[str, ResearchAgent] = {}
        self.events: list = []
        self._load()

    def _load(self):
        if GENE_POOL_FILE.exists():
            try:
                data = json.loads(GENE_POOL_FILE.read_text())
                for a_data in data.get("agents", []):
                    agent = ResearchAgent(**a_data)
                    self.agents[agent.agent_id] = agent
                self.events = data.get("events", [])
            except Exception:
                pass

    def _save(self):
        data = {
            "agents": [
                {
                    "agent_id": a.agent_id, "team": a.team, "domain": a.domain,
                    "prompt": a.prompt, "weight": a.weight, "state": a.state,
                    "G_score": a.G_score, "success_count": a.success_count,
                    "fail_count": a.fail_count, "born_at": a.born_at,
                    "last_active": a.last_active, "generation": a.generation,
                    "specialization": a.specialization,
                }
                for a in self.agents.values()
            ],
            "events": self.events[-100:],
        }
        GENE_POOL_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def spawn_agent(self, team: str = None) -> ResearchAgent:
        """繁殖新Agent。"""
        if not team:
            # 随机团队
            team = random.choice(list(EXPERT_TEAMS.keys()))

        info = EXPERT_TEAMS[team]
        agent_id = hashlib.md5(f"{team}:{time.time()}:{random.random()}".encode()).hexdigest()[:12]

        agent = ResearchAgent(
            agent_id=agent_id,
            team=team,
            domain=info["domain"],
            prompt=info["prompt"],
            weight=info["weight"],
        )
        self.agents[agent_id] = agent
        self.events.append({"type": "spawn", "agent_id": agent_id, "team": team, "time": time.time()})
        self._save()
        return agent

    def wake_or_spawn(self, team: str) -> ResearchAgent:
        """优先唤醒同部门休眠Agent，或找活跃但空闲的。没有则繁殖。"""
        # 1. 找同部门的活跃Agent（优先复用）
        for agent in self.agents.values():
            if agent.team == team and agent.state == "active":
                agent.last_active = time.time()
                return agent  # 复用已有Agent，不繁殖

        # 2. 找同部门的休眠Agent
        for agent in self.agents.values():
            if agent.team == team and agent.state == "hibernating":
                agent.state = "active"
                agent.last_active = time.time()
                self.events.append({"type": "wake", "agent_id": agent.agent_id, "team": team})
                self._save()
                return agent

        # 3. 都没有 → 繁殖
        return self.spawn_agent(team)

    def assign_agents(self, query: str, max_agents: int = 5) -> list[ResearchAgent]:
        """根据问题选择最合适的Agent团队。"""
        # 先看哪些部门与问题相关
        team_scores = {}
        for team_name, info in EXPERT_TEAMS.items():
            score = info["weight"]  # base weight
            # 促进相关部门的匹配
            for kw in info["prompt"].split("从")[-1].split("角度")[0].split("/"):
                kw = kw.strip()
                if kw and kw in query:
                    score += 5
            team_scores[team_name] = score

        # 选Top-N部门
        sorted_teams = sorted(team_scores.items(), key=lambda x: x[1], reverse=True)
        selected = sorted_teams[:max_agents]

        agents = []
        for team_name, _ in selected:
            agent = self.wake_or_spawn(team_name)
            agents.append(agent)

        return agents

    def evaluate_agent(self, agent: ResearchAgent, success: bool, quality: float, 
                        uniqueness: float = 0.5):
        """
        评估Agent表现。
        quality: 报告质量 (0-1)
        uniqueness: 与其他Agent的差异化程度 (0-1)
        """
        if success:
            agent.success_count += 1
            # G = 质量 × 独特性 × 增量 + 惯性
            delta = quality * uniqueness * 1.0
            agent.G_score = min(10.0, agent.G_score + delta)
            # 专长积累
            if quality > 0.7:
                agent.specialization = f"{agent.domain}·{agent.team}"
        else:
            agent.fail_count += 1
            agent.G_score = max(0.0, agent.G_score - 1.0)

        agent.last_active = time.time()
        agent.generation += 1

        # 淘汰检查
        if agent.G_score < self.ELIMINATE_THRESHOLD and agent.fail_count > 3:
            # 先存错配库
            self._save_mismatch(agent)
            agent.state = "eliminated"
            self.events.append({"type": "eliminate", "agent_id": agent.agent_id, "team": agent.team})

        # 休眠检查
        if agent.state == "active" and (time.time() - agent.last_active) > self.HIBERNATE_IDLE:
            agent.state = "hibernating"
            self.events.append({"type": "hibernate", "agent_id": agent.agent_id, "team": agent.team})

        self._save()

    def _save_mismatch(self, agent: ResearchAgent):
        """存入错配储备库——可能只是放错了部门。"""
        repo = {}
        if MISMATCH_FILE.exists():
            try:
                repo = json.loads(MISMATCH_FILE.read_text())
            except Exception:
                pass

        repo[agent.agent_id] = {
            "team": agent.team, "domain": agent.domain,
            "G_score": agent.G_score, "success_count": agent.success_count,
            "specialization": agent.specialization, "eliminated_at": time.time(),
        }
        MISMATCH_FILE.write_text(json.dumps(repo, ensure_ascii=False, indent=2))

    def get_population_stats(self) -> dict:
        active = sum(1 for a in self.agents.values() if a.state == "active")
        hibernating = sum(1 for a in self.agents.values() if a.state == "hibernating")
        eliminated = sum(1 for a in self.agents.values() if a.state == "eliminated")
        avg_g = sum(a.G_score for a in self.agents.values()) / max(1, len(self.agents))
        return {
            "total": len(self.agents),
            "active": active, "hibernating": hibernating, "eliminated": eliminated,
            "avg_G": round(avg_g, 2),
        }


# ════════════════════════════════════════════════════════
#  ResearchAgent — 独立研究执行
# ════════════════════════════════════════════════════════

def agent_research(agent: ResearchAgent, query: str) -> dict:
    """
    一个Agent从自己的专家视角执行全研究流水线。
    返回该Agent的研究报告。
    """
    from engine import (
        dingqing_attend, tianshu_verify, sinanshu_check,
        quantum_consensus, ThermodynamicEngine, page_curve_check,
    )
    from deep import execute_sub_query, decompose_query
    from voyager_llm import safe_llm_call as _llm_call
    from voyager_bridge import grade_sub_results, measure_entropy

    t0 = time.time()

    # Agent特定的分解prompt
    system = f"""你是织星研究团队中的{agent.team}。
你的专业视角：{agent.prompt}。
请从你的专业角度出发，将用户问题拆解为2-3个具体的子问题。
输出每行一个子问题，不要序号。"""

    sub_queries_raw = _llm_call(system, query, max_tokens=200)
    if not sub_queries_raw:
        sub_queries_raw = query

    sub_queries = []
    for line in sub_queries_raw.strip().split("\n"):
        line = line.strip()
        if line and len(line) > 3:
            import re
            line = re.sub(r'^[\d\.\、\)\s]+', '', line).strip()
            if line:
                sub_queries.append(line)

    if not sub_queries:
        sub_queries = [query]

    # 并行执行子查询
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        sub_results = list(pool.map(execute_sub_query, sub_queries))

    # 评分
    sub_results = grade_sub_results(sub_results)

    # Agent特定的综合
    context_parts = []
    for sr in sub_results:
        context_parts.append(f"【{sr['query']}】[{sr.get('source','?')}] {sr['result'][:300]}")
    context = "\n\n".join(context_parts)

    synthesis_prompt = f"""你是{agent.team}（{agent.prompt}）。
根据以下研究结果，从你的专业角度给出分析结论。
简洁、专业、引用数据。"""

    synthesis = _llm_call(synthesis_prompt, f"原始问题: {query}\n\n研究结果:\n{context}", max_tokens=400)

    return {
        "agent_id": agent.agent_id,
        "team": agent.team,
        "domain": agent.domain,
        "weight": agent.weight,
        "G_score": agent.G_score,
        "sub_queries": sub_queries,
        "sub_results": sub_results,
        "synthesis": synthesis or f"[{agent.team}] 分析未能完成",
        "time": round(time.time() - t0, 2),
    }


# ════════════════════════════════════════════════════════
#  DemocraticVote — Agent投票综合
# ════════════════════════════════════════════════════════

def democratic_vote(agent_reports: list, query: str) -> dict:
    """
    民主投票综合。
    每票权重 = Agent.G_score × team_weight / 100。
    三权分立：Agent提议 → 投票 → 审计。
    """
    from voyager_llm import safe_llm_call as _llm_call

    if not agent_reports:
        return {"verdict": "无结论", "votes": [], "consensus": 0}

    # 各Agent提交分析
    proposals = []
    for r in agent_reports:
        vote_weight = r["G_score"] * r["weight"] / 100
        proposals.append({
            "agent_id": r["agent_id"],
            "team": r["team"],
            "weight": round(vote_weight, 2),
            "synthesis": r["synthesis"][:300],
        })

    # 投资委员会综合（模拟）
    context = "\n\n---\n\n".join([
        f"【{p['team']}·权重{p['weight']}】\n{p['synthesis']}"
        for p in proposals
    ])

    verdict_prompt = f"""你是投资委员会主席。以下各部门独立研究后提交了分析报告。
请综合所有意见，给出最终结论。要求：
1. 标注同意哪些部门的观点
2. 对不同意见做裁决
3. 最终建议简洁有力"""

    verdict = _llm_call(verdict_prompt, f"原始问题: {query}\n\n各部门报告:\n{context}", max_tokens=800)

    # 计算共识度
    weights = [p["weight"] for p in proposals]
    consensus = 1.0 - (max(weights) - min(weights)) / (max(weights) + 0.01) if len(weights) > 1 else 1.0

    # 审计：检查是否有Agent串通（报告太相似）
    import re
    similarities = []
    for i in range(len(proposals)):
        for j in range(i+1, len(proposals)):
            a = proposals[i]["synthesis"]
            b = proposals[j]["synthesis"]
            if a and b:
                # 简单 bigram Jaccard
                def bigrams(s):
                    return set(s[k:k+2] for k in range(len(s)-1))
                ba, bb = bigrams(a[:300]), bigrams(b[:300])
                u = len(ba | bb)
                sim = len(ba & bb) / u if u > 0 else 0
                similarities.append(sim)

    avg_sim = sum(similarities) / len(similarities) if similarities else 0
    collusion_warning = avg_sim > 0.6

    return {
        "verdict": verdict or "未能达成共识",
        "votes": proposals,
        "consensus": round(consensus, 3),
        "collusion_warning": collusion_warning,
        "avg_similarity": round(avg_sim, 3),
    }


# ════════════════════════════════════════════════════════
#  CarnotBudget — 全局热力学预算
# ════════════════════════════════════════════════════════

class CarnotBudget:
    """全局信任制冷机预算。"""

    def __init__(self, total_budget: float = 5000.0, tau_hot: float = 0.7, tau_cold: float = 0.2):
        self.total = total_budget
        self.spent = 0.0
        self.tau_hot = tau_hot
        self.tau_cold = tau_cold
        self.allocations: dict[str, float] = {}  # agent_id → budget

    @property
    def carnot_cop(self) -> float:
        delta = self.tau_hot - self.tau_cold
        return self.tau_cold / delta if delta > 0 else float("inf")

    def allocate(self, agents: list, min_per_agent: float = 200) -> dict:
        """按Agent权重分配预算。"""
        total_weight = sum(a.weight for a in agents)
        allocations = {}

        for agent in agents:
            share = agent.weight / total_weight if total_weight > 0 else 0
            budget = max(min_per_agent, share * (self.total - self.spent))
            allocations[agent.agent_id] = min(budget, self.total - self.spent)
            self.allocations[agent.agent_id] = allocations[agent.agent_id]

        return allocations

    def spend(self, agent_id: str, cost: float):
        self.spent += cost
        if agent_id in self.allocations:
            self.allocations[agent_id] -= cost

    def remaining(self) -> float:
        return max(0, self.total - self.spent)

    def efficiency(self) -> float:
        """实际COP vs Carnot COP。"""
        if self.spent == 0:
            return 1.0
        # 实际信任产出 = 1/花费（近似）
        actual_cop = (self.total - self.spent) / self.spent if self.spent > 0 else float("inf")
        return min(1.0, actual_cop / self.carnot_cop) if self.carnot_cop < float("inf") else 1.0


# ════════════════════════════════════════════════════════
#  演化群落主函数
# ════════════════════════════════════════════════════════

# 全局基因池（单例）
_gene_pool: Optional[GenePool] = None


def get_gene_pool() -> GenePool:
    global _gene_pool
    if _gene_pool is None:
        _gene_pool = GenePool()
    return _gene_pool


def evo_deep_research(query: str, max_agents: int = 5) -> dict:
    """
    演化群落深度研究 — Phase 2。
    
    工作流:
    ① GenePool: 分配研究Agent
    ② CarnotBudget: 按权重分配预算
    ③ 各Agent独立研究 (并行)
    ④ DemocraticVote: 投票综合
    ⑤ Evolution: 存优汰劣
    """
    t0 = time.time()
    gene_pool = get_gene_pool()
    budget = CarnotBudget()

    # ── ① 分配Agent ──
    agents = gene_pool.assign_agents(query, max_agents)
    if not agents:
        # 冷启动：繁殖第一批Agent
        for team in list(EXPERT_TEAMS.keys())[:max_agents]:
            agents.append(gene_pool.spawn_agent(team))

    pop_stats = gene_pool.get_population_stats()
    print(f"[了了·演化] ① 种群: {pop_stats['total']} Agent "
          f"(活跃{pop_stats['active']} 休眠{pop_stats['hibernating']} 淘汰{pop_stats['eliminated']})")
    print(f"[了了·演化] ① 分配: {len(agents)} Agent → {[a.team for a in agents]}")

    # ── ② 预算分配 ──
    allocations = budget.allocate(agents)
    print(f"[了了·演化] ② 预算: {budget.total} COP={budget.carnot_cop:.2f}")

    # ── ③ 并行研究 ──
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(agents))) as pool:
        futures = {pool.submit(agent_research, agent, query): agent for agent in agents}
        agent_reports = []
        agent_results = {}  # agent_id → report

        for future in concurrent.futures.as_completed(futures):
            agent = futures[future]
            try:
                report = future.result(timeout=60)
                agent_reports.append(report)
                agent_results[agent.agent_id] = report

                # 记账
                cost = report["time"] * 10  # 每秒10信任单位
                budget.spend(agent.agent_id, cost)
                print(f"[了了·演化] ③ {agent.team}({agent.agent_id[:6]}) "
                      f"完成 {report['time']}s 消耗{cost:.0f}")
            except Exception as e:
                print(f"[了了·演化] ③ {agent.team} 失败: {e}")
                gene_pool.evaluate_agent(agent, False, 0)

    print(f"[了了·演化] ③ 完成: {len(agent_reports)}/{len(agents)} Agent 返回报告")

    # ── ④ 民主投票 ──
    vote = democratic_vote(agent_reports, query)
    print(f"[了了·演化] ④ 投票: 共识={vote['consensus']:.2f} "
          f"串通={'⚠' if vote['collusion_warning'] else '✓'}")

    # ── ⑤ 演化 ──
    # 计算每个Agent的独特性（与其他Agent报告的Jaccard距离均值）
    for agent in agents:
        if agent.agent_id not in agent_results:
            gene_pool.evaluate_agent(agent, False, 0)
            continue

        report = agent_results[agent.agent_id]
        quality = min(1.0, len(report.get("synthesis", "")) / 300)

        # 计算独特性：1 - 与其他报告的平均相似度
        uniqueness = 0.5  # 默认中等
        my_text = report.get("synthesis", "")
        if my_text and len(agent_reports) > 1:
            others = [r.get("synthesis", "") for r in agent_reports 
                      if r["agent_id"] != agent.agent_id]
            sims = []
            for other_text in others:
                if other_text:
                    def bigrams(s):
                        return set(s[k:k+2] for k in range(len(s)-1))
                    ba = bigrams(my_text[:300])
                    bb = bigrams(other_text[:300])
                    u = len(ba | bb)
                    sim = len(ba & bb) / u if u > 0 else 0
                    sims.append(sim)
            if sims:
                avg_sim = sum(sims) / len(sims)
                uniqueness = 1.0 - avg_sim  # 低相似 = 高独特性

        gene_pool.evaluate_agent(agent, True, quality, uniqueness)

    pop_stats_after = gene_pool.get_population_stats()
    print(f"[了了·演化] ⑤ 演化后: 活跃{pop_stats_after['active']} "
          f"平均G={pop_stats_after['avg_G']}")

    total_time = round(time.time() - t0, 2)

    return {
        "query": query,
        "method": "evolutionary_community",
        "population": pop_stats_after,
        "agents_deployed": [a.team for a in agents],
        "agent_reports": agent_reports,
        "verdict": vote["verdict"],
        "vote_details": {
            "consensus": vote["consensus"],
            "collusion_warning": vote["collusion_warning"],
            "avg_similarity": vote["avg_similarity"],
            "votes": vote["votes"],
        },
        "budget": {
            "total": budget.total,
            "spent": round(budget.spent, 1),
            "remaining": round(budget.remaining(), 1),
            "carnot_cop": round(budget.carnot_cop, 2),
            "efficiency": round(budget.efficiency(), 3),
        },
        "stats": {
            "total_time": total_time,
            "agents_count": len(agents),
            "reports_count": len(agent_reports),
            "engine_version": "2.0-evolutionary",
        },
    }


# ═══ 自检 ═══
if __name__ == "__main__":
    result = evo_deep_research("比亚迪和特斯拉哪个更值得投资", max_agents=5)
    print(f"\n{'='*60}")
    print(f"演化研究完成 · {result['stats']['total_time']}s")
    print(f"部署: {result['agents_deployed']}")
    print(f"共识: {result['vote_details']['consensus']:.2f}")
    print(f"种群: {result['population']}")
    print(f"预算: {result['budget']['spent']}/{result['budget']['total']} "
          f"(效率={result['budget']['efficiency']:.2%})")
    print(f"\n裁决 ({len(result['verdict'])}字): {result['verdict'][:300]}...")
