#!/usr/bin/env python3
"""
Counterfactual Research Engine — 知纹 (Zhiwen) Pipeline Module

Tests the robustness of a reasoning chain by perturbing premises and
quantifying how sensitive the conclusion is to each input assumption.
Uses only the Python standard library.
"""

import json
import math
import random
from typing import Any


class CounterfactualEngine:
    """Assesses reasoning-chain robustness via sensitivity, vulnerability,
    joint perturbation bounds, and Monte Carlo flip-rate analysis."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_sensitivity(
        self, premises: list[dict], conclusion_value: float
    ) -> list[dict]:
        """Compute per-premise sensitivity scores.

        Each premise dict must contain: name, value, sigma, dZ_dA.
        Returns the same list with 'sensitivity' and 'delta' fields added.

        s_i  = |∂Z/∂A_i| * σ_i / |Z|
        δ_i  = σ_i / s_i   (the perturbation needed to change Z by one sigma)
        """
        abs_z = abs(conclusion_value)
        if abs_z == 0.0:
            # Degenerate case – Z is zero, sensitivity is formally infinite.
            # We fall back to a very large finite number so downstream code
            # can still operate.
            abs_z = 1e-12

        result: list[dict] = []
        for p in premises:
            name = p["name"]
            value = p["value"]
            sigma = float(p["sigma"])
            dZ_dA = float(p["dZ_dA"])
            s_i = abs(dZ_dA) * sigma / abs_z
            delta_i = sigma / s_i if s_i > 0 else float("inf")
            result.append(
                {
                    "name": name,
                    "value": value,
                    "sigma": sigma,
                    "dZ_dA": dZ_dA,
                    "sensitivity": s_i,
                    "delta": delta_i,
                }
            )
        return result

    def locate_vulnerability(self, chain_partials: list[float]) -> dict:
        """Locate the most vulnerable step in a reasoning chain.

        chain_partials  – list of |∂B_k / ∂B_{k-1}| for each inference step.
        Returns a dict with per-step vulnerability scores, the index of the
        maximally vulnerable step, and a stability flag.
        """
        if not chain_partials:
            return {
                "vulnerabilities": [],
                "max_idx": -1,
                "max_value": 0.0,
                "is_chain_stable": True,
            }

        vulns: list[float] = []
        is_stable = True
        for c in chain_partials:
            c_abs = abs(c)
            # Vulnerability is simply the magnitude; > 1 means the step
            # amplifies upstream noise rather than attenuating it.
            vulns.append(c_abs)
            if c_abs >= 1.0:
                is_stable = False

        max_val = max(vulns)
        max_idx = vulns.index(max_val)

        return {
            "vulnerabilities": vulns,
            "max_idx": max_idx,
            "max_value": max_val,
            "is_chain_stable": is_stable,
        }

    def joint_robustness(self, partials: list[float], Z: float) -> dict:
        """Compute joint perturbation bounds.

        Given the chain partial derivatives |∂B_k/∂B_{k-1}| and the conclusion
        value Z, estimate the worst-case and best-case relative change when
        *all* steps are perturbed simultaneously.

        delta_worst  – worst-case (perturbations all align in same direction).
        delta_best   – best-case  (perturbations cancel maximally).
        """
        if not partials:
            return {"delta_worst": 0.0, "delta_best": 0.0}

        # Cascade factor: how a unit perturbation at step k propagates to Z.
        # Starting from the last step backwards:
        #   factor_k = product of partials from k+1 to end
        #   (factor for the last step is 1.0)
        n = len(partials)
        cascade = [1.0] * n
        for i in range(n - 2, -1, -1):
            cascade[i] = cascade[i + 1] * abs(partials[i + 1])

        delta_worst = sum(cascade)  # all signs align → sum
        delta_best = 0.0
        if n > 1:
            # Best case: biggest factor minus all others (maximal cancellation)
            cascade_sorted = sorted(cascade, reverse=True)
            delta_best = max(0.0, cascade_sorted[0] - sum(cascade_sorted[1:]))

        return {"delta_worst": delta_worst, "delta_best": delta_best}

    def monte_carlo_flip_rate(
        self,
        premises: list[dict],
        Z_nominal: float,
        n_sim: int = 10000,
    ) -> dict:
        """Estimate the probability that the conclusion *sign* flips under
        Gaussian premise perturbations via Monte Carlo simulation.

        Each premise is perturbed:  ε_i ~ N(0, σ_i).
        Linearised Z' = Z_nominal + Σ (∂Z/∂A_i * ε_i).

        Returns flip_rate, raw counts, and a colour-coded grade.
        """
        if Z_nominal == 0.0:
            # With a nominal value of zero, *every* perturbation causes a
            # sign flip (from 0 to something non-zero).  Treat as maximally
            # fragile.
            return {
                "flip_rate": 1.0,
                "flips": n_sim,
                "total": n_sim,
                "grade": "\U0001f534脆弱",  # 🔴
                "n_sim": n_sim,
            }

        # Pre-extract values for speed
        sg: list[tuple[float, float]] = []
        for p in premises:
            sg.append((float(p["sigma"]), float(p["dZ_dA"])))

        flips = 0
        sign_nominal = 1 if Z_nominal > 0 else -1

        for _ in range(n_sim):
            delta_z = 0.0
            for sigma, dZ_dA in sg:
                if sigma > 0:
                    delta_z += dZ_dA * random.gauss(0.0, sigma)
            z_prime = Z_nominal + delta_z
            if (z_prime >= 0) != (Z_nominal > 0):
                flips += 1

        flip_rate = flips / n_sim
        grade = self._grade(flip_rate)

        return {
            "flip_rate": flip_rate,
            "flips": flips,
            "total": n_sim,
            "grade": grade,
            "n_sim": n_sim,
        }

    def assess(self, reasoning_chain: dict) -> dict:
        """Full counterfactual assessment of a reasoning chain.

        Input format (from 知纹 reasoning_engine.py):
        {
            "premises": [
                {"name": str, "value": float, "sigma": float, "dZ_dA": float},
                ...
            ],
            "chain_partials": [float, ...],   # |∂ step_k / ∂ step_{k-1}|
            "Z": float,                        # conclusion value
            "conclusion_text": str
        }

        Returns a comprehensive dict with all metrics and an overall grade.
        """
        premises = reasoning_chain.get("premises", [])
        chain_partials = reasoning_chain.get("chain_partials", [])
        Z = float(reasoning_chain.get("Z", 0.0))
        conclusion_text = reasoning_chain.get("conclusion_text", "")

        # 1. Sensitivity analysis
        sens_premises = self.compute_sensitivity(premises, Z)
        max_sens = max((p["sensitivity"] for p in sens_premises), default=0.0)
        max_sens_name = ""
        for p in sens_premises:
            if p["sensitivity"] == max_sens:
                max_sens_name = p["name"]
                break

        sensitivity_analysis = {
            "premises": sens_premises,
            "max_sensitivity_premise": max_sens_name,
            "max_sensitivity": max_sens,
        }

        # 2. Vulnerability
        vulnerability = self.locate_vulnerability(chain_partials)

        # 3. Joint robustness
        joint_rob = self.joint_robustness(chain_partials, Z)

        # 4. Monte Carlo
        mc = self.monte_carlo_flip_rate(premises, Z)

        # 5. Overall grade – worst of all signals
        overall_grade = self._overall_grade(
            flip_rate=mc["flip_rate"],
            is_stable=vulnerability["is_chain_stable"],
            max_sensitivity=max_sens,
        )

        # 6. Human-readable summary
        summary = self._build_summary(
            mc_grade=mc["grade"],
            stable=vulnerability["is_chain_stable"],
            max_sens_name=max_sens_name,
            flip_rate=mc["flip_rate"],
            conclusion=conclusion_text,
        )

        return {
            "sensitivity_analysis": sensitivity_analysis,
            "vulnerability": vulnerability,
            "joint_robustness": joint_rob,
            "monte_carlo": mc,
            "overall_grade": overall_grade,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _grade(flip_rate: float) -> str:
        if flip_rate < 0.01:
            return "\U0001f7e2稳健"  # 🟢
        elif flip_rate < 0.10:
            return "\U0001f7e1临界"  # 🟡
        else:
            return "\U0001f534脆弱"  # 🔴

    @staticmethod
    def _overall_grade(
        flip_rate: float, is_stable: bool, max_sensitivity: float
    ) -> str:
        """Worst-case grade across all metrics.

        - flip_rate >= 0.10          → 🔴
        - flip_rate >= 0.01          → 🟡 (unless upgraded by stability)
        - chain unstable             → penalise
        - max_sensitivity > 1.0      → penalise
        """
        if flip_rate >= 0.10 or max_sensitivity > 2.0:
            return "\U0001f534脆弱"
        if flip_rate >= 0.01 or max_sensitivity > 1.0 or not is_stable:
            return "\U0001f7e1临界"
        return "\U0001f7e2稳健"

    @staticmethod
    def _build_summary(
        mc_grade: str,
        stable: bool,
        max_sens_name: str,
        flip_rate: float,
        conclusion: str,
    ) -> str:
        grade_icon = mc_grade[0]  # first char is the emoji
        stability_word = "稳定" if stable else "脆弱"
        snippet = conclusion[:40] + ("…" if len(conclusion) > 40 else "")
        return (
            f"{grade_icon} 结论“{snippet}”翻转率 {flip_rate:.1%}，"
            f"链条{stability_word}，最敏感前提：{max_sens_name}"
        )


# ======================================================================
# Demo / self-test
# ======================================================================
if __name__ == "__main__":
    engine = CounterfactualEngine()

    # A sample reasoning chain about an economic policy conclusion
    chain: dict[str, Any] = {
        "premises": [
            {
                "name": "GDP growth forecast",
                "value": 2.5,
                "sigma": 0.8,       # high uncertainty
                "dZ_dA": 1.2,       # positive contribution to conclusion
            },
            {
                "name": "Inflation rate",
                "value": 3.1,
                "sigma": 0.3,       # well-measured
                "dZ_dA": -0.9,      # dampens the conclusion
            },
            {
                "name": "Consumer confidence index",
                "value": 105.0,
                "sigma": 5.0,       # survey noise
                "dZ_dA": 0.05,      # small effect
            },
        ],
        "chain_partials": [1.1, 0.95, 0.88],  # slightly amplifying first step
        "Z": 2.04,  # net conclusion value (positive → "policy is beneficial")
        "conclusion_text": "Expansionary policy is net-beneficial under current conditions",
    }

    report = engine.assess(chain)

    print("=" * 65)
    print("   Counterfactual Research Engine — Assessment Report")
    print("=" * 65)
    print()

    # Sensitivity
    sa = report["sensitivity_analysis"]
    print("─ Sensitivity Analysis ─")
    for p in sa["premises"]:
        print(
            f"  {p['name']:<30s} "
            f"sensitivity = {p['sensitivity']:.3f}  "
            f"δ = {p['delta']:.3f}"
        )
    print(f"  → Most sensitive premise: {sa['max_sensitivity_premise']}")
    print()

    # Vulnerability
    vuln = report["vulnerability"]
    print("─ Chain Vulnerability ─")
    for i, v in enumerate(vuln["vulnerabilities"]):
        marker = " <== MAX" if i == vuln["max_idx"] else ""
        print(f"  Step {i}: |∂| = {v:.3f}{marker}")
    print(f"  Chain stable: {vuln['is_chain_stable']}")
    print()

    # Joint robustness
    jr = report["joint_robustness"]
    print("─ Joint Robustness ─")
    print(f"  δ_worst = {jr['delta_worst']:.3f}")
    print(f"  δ_best  = {jr['delta_best']:.3f}")
    print()

    # Monte Carlo
    mc = report["monte_carlo"]
    print("─ Monte Carlo Flip-Rate ─")
    print(f"  Simulations: {mc['total']}")
    print(f"  Flips:       {mc['flips']}")
    print(f"  Flip rate:   {mc['flip_rate']:.4f}  ({mc['flip_rate']:.2%})")
    print(f"  Grade:       {mc['grade']}")
    print()

    # Overall
    print("─ Overall ─")
    print(f"  Grade:   {report['overall_grade']}")
    print(f"  Summary: {report['summary']}")
    print()
    print("=" * 65)

    # Also dump as JSON for programmatic consumption
    print("\n[JSON]")
    print(json.dumps(report, ensure_ascii=False, indent=2))
