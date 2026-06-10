"""
织星财政模拟器 — MMT优化六点工程落地
虚拟经济体 · φ熵场 · 定倾κ · Carnot预算 · 基因演化 · 民主投票
"""

import json
import math
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent
DATA_DIR = BASE / "data" / "fiscal_sim"
DATA_DIR.mkdir(parents=True, exist_ok=True)

random.seed(42)


# ════════════════════════════════════════════════════════
# 虚拟经济体
# ════════════════════════════════════════════════════════

@dataclass
class Economy:
    """一个虚拟经济体——对应一组财政政策参数。"""
    name: str
    # 政策参数
    deficit_ratio: float      # 赤字率 (0-1)
    spending_infra: float     # 基建占比
    spending_welfare: float   # 福利占比
    spending_military: float  # 军费占比
    tax_rate: float           # 税率

    # 状态变量
    gdp: float = 100.0        # GDP (初始100)
    inflation: float = 0.02   # 通胀率
    unemployment: float = 0.05  # 失业率
    debt_gdp_ratio: float = 0.6  # 债务/GDP

    # 织星度量
    phi: float = 0.3          # 熵场(0-1, 高=过热)
    tau: float = 0.55         # 信任温度
    kappa: float = 0.5        # 支出惯性(加权)
    carnot_budget: float = 100.0  # 剩余信任预算
    G_score: float = 5.0      # 综合评分

    # 历史
    history: list = field(default_factory=list)
    generation: int = 0


# ════════════════════════════════════════════════════════
# 核心模拟引擎
# ════════════════════════════════════════════════════════

class FiscalSimulator:
    """财政政策模拟器：六个优化维度的工程实现。"""

    # 支出惯性 κ (定倾) — 不同支出类型的通胀压力
    KAPPA_MAP = {
        "infra": 0.85,     # 基建: 高惯性，沉淀为产能
        "welfare": 0.35,   # 福利: 低惯性，直接进入消费
        "military": 0.50,  # 军费: 中等惯性
    }

    # Carnot 极限参数
    CARNOT_TAU_HOT = 0.7
    CARNOT_TAU_COLD = 0.2

    def __init__(self):
        self.economies: list[Economy] = []
        self.round = 0
        self.evolution_log: list = []

    def create_initial_population(self, n: int = 8) -> list[Economy]:
        """创建初始政策种群。"""
        templates = [
            ("MMT激进", 0.12, 0.50, 0.35, 0.05, 0.25),
            ("MMT稳健", 0.06, 0.55, 0.30, 0.05, 0.28),
            ("凯恩斯派", 0.04, 0.40, 0.35, 0.15, 0.30),
            ("赤字鹰派", 0.01, 0.30, 0.40, 0.20, 0.32),
            ("供给学派", 0.02, 0.25, 0.30, 0.30, 0.22),
            ("福利国家", 0.08, 0.35, 0.50, 0.05, 0.35),
            ("产业政策", 0.07, 0.60, 0.25, 0.08, 0.27),
            ("平衡预算", 0.00, 0.40, 0.40, 0.10, 0.30),
        ]

        economies = []
        for i, (name, deficit, infra, welfare, military, tax) in enumerate(templates):
            eco = Economy(
                name=f"{name}",
                deficit_ratio=deficit + random.uniform(-0.02, 0.02),
                spending_infra=infra,
                spending_welfare=welfare,
                spending_military=military,
                tax_rate=tax + random.uniform(-0.02, 0.02),
            )
            economies.append(eco)

        self.economies = economies
        return economies

    def compute_kappa(self, eco: Economy) -> float:
        """计算支出惯性 κ = 加权平均。"""
        total = eco.spending_infra + eco.spending_welfare + eco.spending_military
        if total == 0:
            return 0.5
        k = (
            eco.spending_infra * self.KAPPA_MAP["infra"]
            + eco.spending_welfare * self.KAPPA_MAP["welfare"]
            + eco.spending_military * self.KAPPA_MAP["military"]
        ) / total
        eco.kappa = round(k, 3)
        return k

    def compute_phi(self, eco: Economy) -> float:
        """
        熵场 φ: 实时过热探测（先行指标，不用等CPI）
        5个信号加权:
        """
        # 1. 通胀趋势
        inflation_signal = min(1.0, eco.inflation / 0.10)
        # 2. 产能利用率（GDP增长加速→过热）
        if eco.history and len(eco.history) >= 2:
            gdp_growth = eco.history[-1].get("gdp_growth", 0.02)
            gdp_signal = min(1.0, max(0, gdp_growth / 0.08))
        else:
            gdp_signal = 0.3
        # 3. 就业压力（失业低→劳动力紧缺→工资通胀）
        employment_signal = max(0, 1.0 - eco.unemployment / 0.03)
        # 4. 债务速度
        debt_signal = min(1.0, eco.debt_gdp_ratio / 2.0)
        # 5. 支出惯性（低κ→热钱多→通胀压力大）
        kappa = self.compute_kappa(eco)
        kappa_signal = 1.0 - kappa  # 低κ=高热钱=高通胀风险

        # φ = 加权
        phi = (
            0.30 * inflation_signal
            + 0.25 * gdp_signal
            + 0.20 * employment_signal
            + 0.15 * debt_signal
            + 0.10 * kappa_signal
        )
        eco.phi = round(min(1.0, max(0.1, phi)), 3)
        return eco.phi

    def compute_tau(self, eco: Economy) -> float:
        """信任温度 τ = ∂η/∂φ。φ越高，τ越高（信任脆弱）。"""
        tau = 0.3 + 0.5 * eco.phi  # 基础0.3 + φ驱动
        eco.tau = round(min(1.0, max(0.1, tau)), 3)
        return eco.tau

    def carnot_check(self, eco: Economy) -> bool:
        """Carnot极限检查：信任提取有物理上限。"""
        delta = self.CARNOT_TAU_HOT - self.CARNOT_TAU_COLD
        cop = self.CARNOT_TAU_COLD / delta if delta > 0 else float("inf")
        
        # 每轮消耗信任预算 = τ·ln2·(赤字率+通胀)
        cost = eco.tau * math.log(2) * (eco.deficit_ratio * 100 + eco.inflation * 100)
        eco.carnot_budget -= cost

        # 预算耗尽→过度透支→强制冷却
        if eco.carnot_budget <= 0:
            eco.deficit_ratio *= 0.7  # 强制减赤
            eco.inflation += 0.02     # 通胀惩罚
            return False
        return True

    def simulate_round(self, eco: Economy) -> dict:
        """模拟一轮经济演化。"""
        kappa = self.compute_kappa(eco)

        # GDP增长 = 基础增长 + 赤字刺激 - 通胀拖累 - 结构性衰减
        stimulus = eco.deficit_ratio * kappa * 0.6  # 赤字×惯性=有效刺激(降低)
        inflation_drag = eco.inflation * 0.8        # 通胀拖累(增大)
        structural_growth = 0.015                    # 自然增长(降低)

        gdp_growth = structural_growth + stimulus - inflation_drag
        eco.gdp *= (1 + gdp_growth)

        # 通胀更新
        hot_money = eco.deficit_ratio * (1 - kappa) * 2.0  # 热钱效应(增大)
        capacity_absorption = eco.spending_infra * 0.4      # 产能吸收
        eco.inflation = max(0.003, eco.inflation * 0.75 + 0.008 + hot_money - capacity_absorption)

        # 失业更新
        eco.unemployment = max(0.02, eco.unemployment - stimulus * 0.3 + 0.002)

        # 债务更新
        eco.debt_gdp_ratio += eco.deficit_ratio - gdp_growth * eco.debt_gdp_ratio

        # 织星度量
        phi = self.compute_phi(eco)
        tau = self.compute_tau(eco)
        can_continue = self.carnot_check(eco)

        # G-score: 综合评分
        # 1. 增长得分 (GDP增长率, 0-3)
        growth_score = min(3, max(0, gdp_growth * 50))
        # 2. 稳定得分 (低通胀, 0-3)
        stability_score = min(3, max(0, 3 - eco.inflation * 60))
        # 3. 就业得分 (低失业, 0-2)
        employment_score = min(2, max(0, 2 - eco.unemployment * 20))
        # 4. 可持续得分 (债务可控, 0-2)
        sustainability_score = min(2, max(0, 2 - eco.debt_gdp_ratio * 1.5))
        
        eco.G_score = round(growth_score + stability_score + employment_score + sustainability_score, 2)
        eco.generation += 1

        result = {
            "round": self.round,
            "economy": eco.name,
            "gdp": round(eco.gdp, 2),
            "gdp_growth": round(gdp_growth, 4),
            "inflation": round(eco.inflation, 4),
            "unemployment": round(eco.unemployment, 4),
            "debt_gdp": round(eco.debt_gdp_ratio, 3),
            "phi": eco.phi,
            "tau": eco.tau,
            "kappa": eco.kappa,
            "carnot_ok": can_continue,
            "G_score": eco.G_score,
        }
        eco.history.append(result)
        return result

    def run_simulation(self, rounds: int = 20) -> list:
        """运行多轮模拟。"""
        if not self.economies:
            self.create_initial_population()

        all_results = []
        for r in range(rounds):
            self.round = r + 1
            round_results = []
            for eco in self.economies:
                result = self.simulate_round(eco)
                round_results.append(result)
            all_results.append(round_results)

        return all_results

    def evolution_cycle(self, rounds: int = 20, select_top: int = 4) -> dict:
        """
        演化周期：N轮→评分→淘汰劣质→繁殖优质→继续。
        """
        # 运行模拟
        all_results = self.run_simulation(rounds)

        # 按最终G-score排名
        self.economies.sort(key=lambda e: e.G_score, reverse=True)

        # Top N 存活
        survivors = self.economies[:select_top]
        eliminated = self.economies[select_top:]

        # 繁殖：Top幸存者交叉变异
        new_population = list(survivors)
        while len(new_population) < 8:
            parent1 = random.choice(survivors)
            parent2 = random.choice(survivors)
            
            # 交叉 + 变异
            child = Economy(
                name=f"演化体-{len(new_population)+1}",
                deficit_ratio=min(0.15, max(0.0, 
                    (parent1.deficit_ratio + parent2.deficit_ratio) / 2 + random.uniform(-0.02, 0.02))),
                spending_infra=max(0.1, min(0.7,
                    (parent1.spending_infra + parent2.spending_infra) / 2 + random.uniform(-0.05, 0.05))),
                spending_welfare=max(0.1, min(0.6,
                    (parent1.spending_welfare + parent2.spending_welfare) / 2 + random.uniform(-0.05, 0.05))),
                spending_military=max(0.02, min(0.3,
                    (parent1.spending_military + parent2.spending_military) / 2 + random.uniform(-0.03, 0.03))),
                tax_rate=min(0.4, max(0.15,
                    (parent1.tax_rate + parent2.tax_rate) / 2 + random.uniform(-0.02, 0.02))),
            )
            new_population.append(child)

        self.economies = new_population

        # 生成报告
        final_ranking = sorted(all_results[-1], key=lambda r: r["G_score"], reverse=True)
        
        return {
            "rounds": rounds,
            "survivors": [{"name": e.name, "G": e.G_score, 
                          "deficit": round(e.deficit_ratio, 3),
                          "infra": round(e.spending_infra, 2),
                          "welfare": round(e.spending_welfare, 2),
                          "phi": e.phi, "kappa": e.kappa,
                          "gdp": round(e.gdp, 2),
                          "inflation": round(e.inflation, 3)}
                         for e in survivors],
            "eliminated": [e.name for e in eliminated],
            "final_ranking": final_ranking[:5],
            "best_policy": final_ranking[0] if final_ranking else None,
        }

    def democratic_vote(self, policies: list[dict]) -> dict:
        """民主投票：选最优财政组合。"""
        if not policies:
            return {"verdict": "无数据"}

        # 投票权重 = G_score
        total_weight = sum(p["G_score"] for p in policies)
        if total_weight == 0:
            return {"verdict": "无有效策略"}

        # 加权平均最优参数
        avg_deficit = sum(p["deficit"] * p["G_score"] for p in policies) / total_weight
        avg_infra = sum(p["infra"] * p["G_score"] for p in policies) / total_weight
        avg_welfare = sum(p["welfare"] * p["G_score"] for p in policies) / total_weight

        # 找到最接近加权平均的实际策略
        best = min(policies, key=lambda p: 
            abs(p["deficit"] - avg_deficit) + abs(p["infra"] - avg_infra))

        return {
            "verdict": f"民主投票最优: {best['name']} (G={best['G_score']:.1f})",
            "recommended_params": {
                "deficit_ratio": round(avg_deficit, 3),
                "spending_infra": round(avg_infra, 2),
                "spending_welfare": round(avg_welfare, 2),
                "reasoning": "高基建(κ=0.85) + 适度福利(κ=0.35) + 赤字率匹配φ",
            },
            "top_policies": [{"name": p["name"], "G": p["G_score"]} for p in sorted(policies, key=lambda x: x["G_score"], reverse=True)[:3]],
        }


# ════════════════════════════════════════════════════════
# 统一入口
# ════════════════════════════════════════════════════════

def run_full_simulation(rounds: int = 20, generations: int = 3) -> dict:
    """完整模拟：多代演化+六维优化。"""
    sim = FiscalSimulator()
    sim.create_initial_population(8)

    all_gen_results = []
    final_best = None

    for gen in range(generations):
        print(f"\n═══ 第{gen+1}代 · {rounds}轮 ═══")
        
        result = sim.evolution_cycle(rounds=rounds)
        all_gen_results.append(result)
        
        # 民主投票
        vote = sim.democratic_vote([{
            "name": s["name"], "G_score": s["G"],
            "deficit": s["deficit"], "infra": s["infra"], "welfare": s["welfare"],
        } for s in result["survivors"]])
        result["vote"] = vote

        print(f"  存活: {[s['name'] + '(G=' + str(s['G']) + ')' for s in result['survivors']]}")
        print(f"  淘汰: {result['eliminated']}")
        print(f"  {vote['verdict']}")

        if gen == generations - 1:
            final_best = result["best_policy"]

    return {
        "generations": generations,
        "rounds_per_gen": rounds,
        "results": all_gen_results,
        "final_recommendation": final_best,
        "summary": {
            "optimal_deficit": final_best.get("deficit") if final_best else None,
            "optimal_infra_ratio": final_best.get("spending_infra") if final_best else None,
            "key_insight": "高κ(基建)支出优先 + 赤字率匹配φ熵场 + Carnot预算约束",
        },
    }


# ═══ 自检 ═══
if __name__ == "__main__":
    t0 = time.time()
    result = run_full_simulation(rounds=15, generations=3)
    t = round(time.time() - t0, 1)
    
    rec = result["final_recommendation"]
    print(f"\n{'='*60}")
    print(f"模拟完成 · {t}s · {result['generations']}代 × {result['rounds_per_gen']}轮")
    print(f"\n最优政策: {rec['economy']}")
    print(f"  G-score: {rec['G_score']}")
    print(f"  GDP: {rec['gdp']}")
    print(f"  通胀: {rec['inflation']}")
    print(f"  φ熵场: {rec['phi']} | τ信任: {rec['tau']} | κ惯性: {rec['kappa']}")
    print(f"  失业率: {rec['unemployment']}")
