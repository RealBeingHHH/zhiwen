"""
通用模拟器适配器 — 任何领域可接入科学方法循环

协议：
  Simulator.run(query: str, params: dict) -> dict
    返回: {"score": float, "metrics": {...}, "full_result": {...}}

  Simulator.param_space() -> dict
    返回: {"param_name": {"type": "float", "min": x, "max": y, "default": z}, ...}

  Simulator.domain_keywords() -> list[str]
    返回: 触发该模拟器的关键词列表
"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


@runtime_checkable
class SimulatorProtocol(Protocol):
    """任何模拟器必须实现这三个方法。"""

    def run(self, query: str, params: dict) -> dict:
        """运行模拟，返回 {'score': float, 'metrics': {...}, 'full_result': {...}}"""
        ...

    def param_space(self) -> dict:
        """参数空间定义 {'name': {'type':'float','min':0,'max':1,'default':0.5}, ...}"""
        ...

    def domain_keywords(self) -> list[str]:
        """触发关键词列表"""
        ...


class SimulatorRegistry:
    """模拟器注册中心。"""

    _simulators: dict[str, object] = {}

    @classmethod
    def register(cls, name: str, simulator) -> None:
        """注册一个模拟器。"""
        cls._simulators[name] = simulator

    @classmethod
    def detect(cls, query: str) -> list[tuple[str, object]]:
        """根据query检测匹配的模拟器。返回 (name, simulator) 列表。"""
        matches = []
        for name, sim in cls._simulators.items():
            keywords = sim.domain_keywords()
            score = sum(1 for k in keywords if k in query)
            if score >= 2:  # 至少匹配2个关键词
                matches.append((name, sim))
        return matches

    @classmethod
    def list_all(cls) -> list[str]:
        """列出所有已注册模拟器。"""
        return list(cls._simulators.keys())


# ════════════════════════════════════════════════════════
# 内置: 经济政策模拟器适配器
# ════════════════════════════════════════════════════════

class FiscalSimAdapter:
    """将 fiscal_sim 包装为通用模拟器协议。"""

    def __init__(self):
        from fiscal_sim import FiscalSimulator
        self._sim = None

    def param_space(self) -> dict:
        return {
            "deficit_ratio": {"type": "float", "min": 0.0, "max": 0.15, "default": 0.05, "label": "赤字率"},
            "spending_infra": {"type": "float", "min": 0.1, "max": 0.8, "default": 0.4, "label": "基建支出占比"},
            "spending_welfare": {"type": "float", "min": 0.1, "max": 0.7, "default": 0.3, "label": "福利支出占比"},
            "tax_rate": {"type": "float", "min": 0.1, "max": 0.5, "default": 0.25, "label": "税率"},
            "kappa": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.5, "label": "定倾κ（基建乘数）"},
        }

    def domain_keywords(self) -> list[str]:
        return [
            "MMT", "财政", "赤字", "通胀", "货币政策", "税收", "税率", "预算",
            "GDP", "支出", "国债", "债务", "赤字率", "就业", "失业",
            "基建", "福利", "补贴", "投资", "公共", "政府",
            "最优", "最佳", "改善", "优化", "策略",
        ]

    def run(self, query: str, params: dict) -> dict:
        """运行财政模拟。params覆盖默认参数。"""
        from fiscal_sim import FiscalSimulator

        sim = FiscalSimulator()
        sim.create_initial_population(8)

        # 将参数映射到经济体
        for eco in sim.economies:
            if "deficit_ratio" in params:
                eco.deficit_ratio = params["deficit_ratio"]
            if "spending_infra" in params:
                eco.spending_infra = params["spending_infra"]
            if "spending_welfare" in params:
                eco.spending_welfare = params["spending_welfare"]
            if "tax_rate" in params:
                eco.tax_rate = params["tax_rate"]
            if "kappa" in params:
                eco.kappa = params["kappa"]

        sim.evolution_cycle(rounds=15)
        result = sim.evolution_cycle(rounds=15)

        best = result.get("best_policy", {})
        return {
            "score": best.get("G_score", 0),
            "metrics": {
                "gdp": best.get("gdp", 0),
                "inflation": best.get("inflation", 0),
                "phi": best.get("phi", 0),
                "kappa": best.get("kappa", 0),
                "unemployment": best.get("unemployment", 0),
            },
            "full_result": result,
        }


# 注册内置模拟器
SimulatorRegistry.register("fiscal", FiscalSimAdapter())


# ════════════════════════════════════════════════════════
# 流行病SIR模拟器
# ════════════════════════════════════════════════════════

class SIRSimAdapter:
    """SIR流行病模型 — 感染·恢复·死亡动力学。"""

    def param_space(self) -> dict:
        return {
            "beta": {"type": "float", "min": 0.05, "max": 0.5, "default": 0.2, "label": "传播率β"},
            "gamma": {"type": "float", "min": 0.02, "max": 0.2, "default": 0.1, "label": "恢复率γ"},
            "mu": {"type": "float", "min": 0.0, "max": 0.05, "default": 0.005, "label": "死亡率μ"},
            "initial_infected": {"type": "float", "min": 0.001, "max": 0.1, "default": 0.01, "label": "初始感染比例"},
            "intervention_strength": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.0, "label": "干预强度"},
        }

    def domain_keywords(self) -> list[str]:
        return [
            "疫情", "感染", "流行病", "传染", "SIR", "传播", "隔离",
            "疫苗", "群体免疫", "R0", "基本再生数", "防控", "公共卫生",
            "最优", "最佳", "策略", "干预",
        ]

    def run(self, query: str, params: dict) -> dict:
        """运行SIR模拟。"""
        beta = params.get("beta", 0.2)
        gamma = params.get("gamma", 0.1)
        mu = params.get("mu", 0.005)
        i0 = params.get("initial_infected", 0.01)
        intervention = params.get("intervention_strength", 0.0)

        # 干预降低传播率
        effective_beta = beta * (1 - intervention * 0.7)

        # 简单SIR模拟（100天）
        S, I, R, D = 1 - i0, i0, 0, 0
        peak_infected = I
        total_infected = I

        for _ in range(100):
            new_infections = effective_beta * S * I
            new_recoveries = gamma * I
            new_deaths = mu * I

            S -= new_infections
            I += new_infections - new_recoveries - new_deaths
            R += new_recoveries
            D += new_deaths

            I = max(0, I)
            total_infected += new_infections
            peak_infected = max(peak_infected, I)

        # 综合评分: 越低的总死亡+越低的峰值 = 越高分
        death_penalty = D * 100
        peak_penalty = peak_infected * 50
        score = max(0, 10 - death_penalty - peak_penalty)

        R0 = effective_beta / (gamma + mu) if (gamma + mu) > 0 else 0

        return {
            "score": round(score, 1),
            "metrics": {
                "R0": round(R0, 2),
                "peak_infected_pct": round(peak_infected * 100, 1),
                "total_death_pct": round(D * 100, 1),
                "final_susceptible": round(S * 100, 1),
                "epidemic_duration": "simulated 100 days",
            },
            "full_result": {},
        }


SimulatorRegistry.register("sir", SIRSimAdapter())


# ════════════════════════════════════════════════════════
# 博弈论囚徒困境模拟器
# ════════════════════════════════════════════════════════

class GameTheoryAdapter:
    """博弈论 — 囚徒困境迭代 + 策略演化。"""

    STRATEGIES = ["always_cooperate", "always_defect", "tit_for_tat", "grim_trigger", "random"]

    def param_space(self) -> dict:
        return {
            "cooperation_reward": {"type": "float", "min": 1, "max": 5, "default": 3, "label": "合作奖励R"},
            "temptation": {"type": "float", "min": 3, "max": 8, "default": 5, "label": "背叛诱惑T"},
            "sucker_payoff": {"type": "float", "min": 0, "max": 2, "default": 0, "label": "受骗惩罚S"},
            "punishment": {"type": "float", "min": 0, "max": 3, "default": 1, "label": "互相背叛P"},
            "rounds": {"type": "int", "min": 10, "max": 200, "default": 50, "label": "轮次"},
        }

    def domain_keywords(self) -> list[str]:
        return [
            "博弈", "囚徒困境", "纳什均衡", "策略", "合作",
            "背叛", "演化", "重复博弈", "最优策略", "选择",
            "搭便车", "公地悲剧", "协调",
        ]

    def run(self, query: str, params: dict) -> dict:
        """运行博弈演化模拟。"""
        R = params.get("cooperation_reward", 3)
        T = params.get("temptation", 5)
        S = params.get("sucker_payoff", 0)
        P = params.get("punishment", 1)
        rounds = int(params.get("rounds", 50))

        # 收益矩阵
        payoff = {
            ("C", "C"): (R, R),
            ("C", "D"): (S, T),
            ("D", "C"): (T, S),
            ("D", "D"): (P, P),
        }

        # 策略定义
        def make_choice(strategy: str, history_self: list, history_opp: list) -> str:
            if strategy == "always_cooperate":
                return "C"
            if strategy == "always_defect":
                return "D"
            if strategy == "grim_trigger":
                if "D" in history_opp:
                    return "D"
                return "C"
            if strategy == "tit_for_tat":
                if not history_opp:
                    return "C"
                return history_opp[-1]
            if strategy == "random":
                import random
                return "C" if random.random() > 0.5 else "D"
            return "C"

        # 所有策略互相博弈
        results = {}
        for s1 in self.STRATEGIES:
            total_score = 0
            for s2 in self.STRATEGIES:
                h1, h2 = [], []
                for _ in range(rounds):
                    c1 = make_choice(s1, h1, h2)
                    c2 = make_choice(s2, h2, h1)
                    s1_score, _ = payoff[(c1, c2)]
                    total_score += s1_score
                    h1.append(c1)
                    h2.append(c2)
            results[s1] = round(total_score / len(self.STRATEGIES), 1)

        best_strategy = max(results.keys(), key=lambda k: results[k])
        best_score = results[best_strategy]

        return {
            "score": round(best_score / (R * rounds), 1),
            "metrics": {
                "best_strategy": best_strategy,
                "strategy_scores": results,
                "nash_condition": T > R > P > S,
                "cooperation_rate": sum(
                    1 for s in self.STRATEGIES if "cooperate" in s or "tit_for_tat" in s
                ) / len(self.STRATEGIES),
            },
            "full_result": {"all_scores": results},
        }


SimulatorRegistry.register("game_theory", GameTheoryAdapter())
