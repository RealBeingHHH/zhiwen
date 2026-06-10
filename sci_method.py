"""
科学方法引擎 v2.0 — 假设→模拟→验证→改善→循环
整合 fiscal_sim + deep_research，持续优化的研究范式

v2.0 拓展:
  - parameter_sweep(): 参数敏感性分析
  - competing_hypotheses(): 多假说竞争→民主选优
  - convergence_html(): 收敛可视化仪表盘
  - 通用模拟器接口 (sim_adapter.py)
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
DATA_DIR = BASE / "data" / "sci_method"
DATA_DIR.mkdir(parents=True, exist_ok=True)

from voyager_llm import safe_llm_call as _llm_call
from fiscal_sim import FiscalSimulator, Economy
from sim_adapter import SimulatorRegistry, FiscalSimAdapter
from relation_integrity import SimulationIntegrity


# ════════════════════════════════════════════════════════
# 实验记录
# ════════════════════════════════════════════════════════

@dataclass
class Experiment:
    """一次完整的假设-模拟-验证-改善循环。"""
    id: str
    query: str              # 原始问题
    hypothesis: str         # LLM生成的假设
    round_num: int          # 第几轮循环
    sim_result: Optional[dict] = None  # 模拟结果
    verification: Optional[dict] = None  # 验证结论
    improvement: Optional[str] = None   # 改善建议
    score: float = 0.0      # 本轮综合评分
    converged: bool = False  # 是否收敛


# ════════════════════════════════════════════════════════
# 核心引擎
# ════════════════════════════════════════════════════════

class ScientificMethod:
    """假设→模拟→验证→改善→循环 + 参数扫描 + 竞争假说 + 可视化"""

    def __init__(self, max_rounds: int = 5, convergence_threshold: float = 0.05):
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.experiments: list[Experiment] = []
        self.best_result: Optional[dict] = None
        self.best_score: float = 0.0
        self._sweep_cache: Optional[dict] = None
        self._competing_cache: Optional[dict] = None

    # ─── ① 参数敏感性扫描 ───

    def parameter_sweep(
        self,
        query: str,
        steps: int = 6,
        sim_name: str = "fiscal",
    ) -> dict:
        """
        参数敏感性分析：逐参数扫描，绘制G-score响应曲线。

        对每个参数：
          - 在 [min, max] 范围内取 `steps` 个点
          - 其他参数保持默认
          - 每个点运行一次模拟 → 记录G-score
        """
        sim = SimulatorRegistry._simulators.get(sim_name)
        if not sim:
            return {"error": f"模拟器 {sim_name} 未注册"}

        param_space = sim.param_space()
        results = {}

        print(f"\n{'='*60}")
        print(f"📊 参数敏感性扫描 · {len(param_space)}参数 × {steps}步")
        print(f"{'='*60}")

        for param_name, spec in param_space.items():
            lo, hi = spec["min"], spec["max"]
            default = spec["default"]
            label = spec.get("label", param_name)
            sweep_points = []
            scores = []

            for i in range(steps):
                val = lo + (hi - lo) * i / (steps - 1)
                val = round(val, 4)

                # 构建参数字典（仅扫描参数变动，其他用默认值）
                params = {p: ps["default"] for p, ps in param_space.items()}
                params[param_name] = val

                result = sim.run(query, params)
                score = result["score"]

                sweep_points.append({
                    "param_value": val,
                    "score": score,
                    "metrics": result["metrics"],
                })
                scores.append(score)
                print(f"  {label} = {val:.3f} → G={score}")

            # 找到最优值
            best_idx = max(range(len(scores)), key=lambda i: scores[i])
            best_point = sweep_points[best_idx]

            # 计算灵敏度 (max-min 跨度)
            sensitivity = round(max(scores) - min(scores), 3)

            results[param_name] = {
                "label": label,
                "range": [lo, hi],
                "default": default,
                "sweep": sweep_points,
                "best_value": best_point["param_value"],
                "best_score": best_point["score"],
                "sensitivity": sensitivity,
            }

            print(f"  → 最优 {label}={best_point['param_value']:.3f} G={best_point['score']} "
                  f"灵敏度={sensitivity}")

        # 综合排序：按灵敏度降序
        ranked = sorted(results.items(), key=lambda kv: kv[1]["sensitivity"], reverse=True)

        self._sweep_cache = {
            "query": query,
            "simulator": sim_name,
            "steps": steps,
            "results": results,
            "ranked_by_sensitivity": [
                {"param": name, "label": data["label"], "sensitivity": data["sensitivity"],
                 "best_value": data["best_value"], "best_score": data["best_score"]}
                for name, data in ranked
            ],
        }
        return self._sweep_cache

    # ─── ② 竞争假说 ───

    def competing_hypotheses(
        self,
        query: str,
        num_hypotheses: int = 3,
        rounds_per: int = 2,
    ) -> dict:
        """
        竞争假说模式：生成N个独立假说，各自跑模拟循环，民主投票选最优。

        流程:
          1. LLM生成 N 个相互竞争的假说
          2. 每个假说独立跑 rounds_per 轮
          3. 综合评分：模拟G-score + LLM民主投票
        """
        print(f"\n{'='*60}")
        print(f"⚔️ 竞争假说模式 · {num_hypotheses}个假说 × {rounds_per}轮/个")
        print(f"{'='*60}")

        # ① 生成竞争假说
        system = f"""你是科学研究员。针对问题生成 {num_hypotheses} 个相互竞争的假说。
这些假说应该：
1. 从不同理论视角出发（彼此矛盾更好）
2. 每个都是可测试的
3. 预期结果相互排斥

输出格式：每行一个假说，不要编号。"""

        raw = _llm_call(system, query, max_tokens=300)
        if not raw:
            return {"error": "LLM生成假说失败"}

        hypotheses = [h.strip() for h in raw.strip().split("\n") if len(h.strip()) > 10]
        hypotheses = hypotheses[:num_hypotheses]
        print(f"  生成 {len(hypotheses)} 个竞争假说")

        # ② 每个假说独立运行
        hypothesis_results = []
        for i, hyp in enumerate(hypotheses):
            print(f"\n  ── 假说{i+1}: {hyp[:80]}... ──")
            engine = ScientificMethod(max_rounds=rounds_per)
            result = engine.run_cycle(hyp, max_rounds=rounds_per)
            hypothesis_results.append({
                "hypothesis": hyp,
                "result": result,
                "best_score": result["best_score"],
                "converged": result["converged"],
            })
            print(f"    最佳G={result['best_score']} 收敛={result['converged']}")

        # ③ LLM民主投票
        voting_prompt = f"""你是科学评审委员会主席。以下{len(hypothesis_results)}个假说互斥，
各自经过模拟验证。请投票选出最优假说并说明理由。

候选假说及其模拟结果：
"""
        for i, hr in enumerate(hypothesis_results):
            r = hr["result"]
            voting_prompt += f"""
假说{i+1}: {hr['hypothesis']}
  G-score: {hr['best_score']}
  收敛: {hr['converged']}
  轮次: {r['rounds']}
  结论: {r['conclusion'][:200]}
"""

        voting_prompt += """
请输出：
第一行：假说编号（如 1）
第二行：投票理由（1-2句）
第三行：融合建议（如何综合各假说的优点）"""

        vote = _llm_call(voting_prompt, query, max_tokens=300) or ""
        vote_lines = vote.strip().split("\n")

        winner_idx = 0
        try:
            winner_idx = int(vote_lines[0].strip()) - 1
        except (ValueError, IndexError):
            pass
        winner_idx = max(0, min(winner_idx, len(hypothesis_results) - 1))

        winner = hypothesis_results[winner_idx]

        print(f"\n  🏆 胜出: 假说{winner_idx+1} (G={winner['best_score']})")
        print(f"     理由: {vote_lines[1] if len(vote_lines) > 1 else 'N/A'}")

        self._competing_cache = {
            "query": query,
            "num_hypotheses": len(hypotheses),
            "hypotheses": hypotheses,
            "results": hypothesis_results,
            "winner_idx": winner_idx,
            "winner_hypothesis": winner["hypothesis"],
            "winner_score": winner["best_score"],
            "vote_reason": vote_lines[1] if len(vote_lines) > 1 else "",
            "fusion_advice": vote_lines[2] if len(vote_lines) > 2 else "",
        }
        return self._competing_cache

    # ─── ③ 收敛可视化 ───

    def convergence_html(self, output_path: Optional[str] = None) -> str:
        """
        生成收敛轨迹可视化HTML（自包含，数据内嵌）。
        基于现有的experiments数据。
        """
        if not self.experiments:
            return "<html><body>无实验数据</body></html>"

        # 构建轨迹数据
        rounds = []
        G_scores = []
        verdicts = []
        for exp in self.experiments:
            rounds.append(exp.round_num)
            G_scores.append(exp.score)
            verdicts.append(exp.verification.get("verdict", "?"))

        trajectory_json = json.dumps({
            "rounds": rounds,
            "G_scores": G_scores,
            "verdicts": verdicts,
            "hypotheses": [e.hypothesis[:80] for e in self.experiments],
        }, ensure_ascii=False)

        html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>科学方法 · 收敛轨迹</title>
<style>
  * {{margin:0;padding:0;box-sizing:border-box}}
  body {{background:#0a0a0f;color:#c8d6e5;font-family:'SF Pro Display',system-ui,sans-serif;padding:24px}}
  h1 {{font-size:18px;color:#48dbfb;margin-bottom:8px}}
  .subtitle {{font-size:12px;color:#576574;margin-bottom:24px}}
  .charts {{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}}
  @media(max-width:800px){{.charts{{grid-template-columns:1fr}}}}
  .card {{background:#12121a;border:1px solid #1e1e2e;border-radius:10px;padding:16px}}
  .card h3 {{font-size:13px;color:#8395a7;margin-bottom:12px}}
  canvas {{width:100%;height:280px}}
  table {{width:100%;border-collapse:collapse;font-size:13px}}
  th,td {{padding:8px 12px;text-align:left;border-bottom:1px solid #1e1e2e}}
  th {{color:#576574;font-weight:500;font-size:11px;text-transform:uppercase}}
  .verdict-support {{color:#00d2d3}}
  .verdict-partial {{color:#feca57}}
  .verdict-against {{color:#ff6b6b}}
  .converged {{color:#00d2d3;font-weight:bold}}
  .stats {{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
  .stat {{background:#12121a;border:1px solid #1e1e2e;border-radius:8px;padding:12px;text-align:center}}
  .stat .value {{font-size:24px;font-weight:700;color:#48dbfb}}
  .stat .label {{font-size:10px;color:#576574;margin-top:4px;text-transform:uppercase}}
</style>
</head>
<body>
<h1>🔬 科学方法 · 收敛轨迹</h1>
<div class="subtitle">假设→模拟→验证→改善→循环</div>
<div class="stats">
  <div class="stat"><div class="value">{len(rounds)}</div><div class="label">轮次</div></div>
  <div class="stat"><div class="value">{max(G_scores):.1f}</div><div class="label">最佳G</div></div>
  <div class="stat"><div class="value">{G_scores[-1] if G_scores else 0:.1f}</div><div class="label">最终G</div></div>
  <div class="stat"><div class="value" class=\"{'converged' if self.experiments[-1].converged else ''}\">{"✅" if self.experiments[-1].converged else "🔄"}</div><div class="label">收敛</div></div>
</div>
<div class="charts">
  <div class="card">
    <h3>G-score 演化</h3>
    <canvas id="gChart"></canvas>
  </div>
  <div class="card">
    <h3>验证裁决分布</h3>
    <canvas id="verdictChart"></canvas>
  </div>
</div>
<div class="card">
  <h3>演化轨迹</h3>
  <table id="trajTable"></table>
</div>
<script>
var DATA = {trajectory_json};
(function() {{
  // 填充表格
  var tbody = '<tr><th>轮</th><th>G-score</th><th>裁决</th><th>假说</th></tr>';
  DATA.rounds.forEach(function(r,i) {{
    var v = DATA.verdicts[i];
    var cls = v==='支持'?'verdict-support':v==='部分支持'?'verdict-partial':'verdict-against';
    tbody += '<tr><td>' + r + '</td><td>' + DATA.G_scores[i].toFixed(1) + '</td>'
          + '<td class=\"' + cls + '\">' + v + '</td>'
          + '<td style=\"font-size:12px\">' + DATA.hypotheses[i] + '</td></tr>';
  }});
  document.getElementById('trajTable').innerHTML = tbody;

  // G-score折线图
  var gc = document.getElementById('gChart');
  if (gc) {{
    var gctx = gc.getContext('2d');
    var W = gc.parentElement.clientWidth - 32;
    var H = 260;
    gc.width = W * 2; gc.height = H * 2;
    gc.style.width = W + 'px'; gc.style.height = H + 'px';
    gctx.scale(2,2);
    var pad = {{l:40, r:20, t:20, b:30}};
    var pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    var gm = Math.max.apply(null, DATA.G_scores), gn = Math.min.apply(null, DATA.G_scores);
    var range = gm - gn || 1;

    // 网格
    gctx.strokeStyle = '#1e1e2e'; gctx.lineWidth = 0.5;
    for (var i=0;i<=4;i++) {{
      var y = pad.t + ph * i/4;
      gctx.beginPath(); gctx.moveTo(pad.l,y); gctx.lineTo(W-pad.r,y); gctx.stroke();
      gctx.fillStyle = '#576574'; gctx.font = '10px system-ui';
      gctx.fillText((gm - range*i/4).toFixed(1), 2, y+3);
    }}

    // 连线
    gctx.strokeStyle = '#48dbfb'; gctx.lineWidth = 2;
    gctx.beginPath();
    DATA.G_scores.forEach(function(s,i) {{
      var x = pad.l + pw * i/(DATA.G_scores.length-1||1);
      var y = pad.t + ph*(1-(s-gn)/range);
      if (i===0) gctx.moveTo(x,y); else gctx.lineTo(x,y);
    }});
    gctx.stroke();

    // 数据点
    DATA.G_scores.forEach(function(s,i) {{
      var x = pad.l + pw * i/(DATA.G_scores.length-1||1);
      var y = pad.t + ph*(1-(s-gn)/range);
      gctx.fillStyle = '#48dbfb'; gctx.beginPath(); gctx.arc(x,y,4,0,Math.PI*2); gctx.fill();
      gctx.fillStyle = '#c8d6e5'; gctx.font = '11px system-ui'; gctx.fillText(s.toFixed(1), x-8, y-10);
    }});
  }}

  // 裁决饼图
  var vc = document.getElementById('verdictChart');
  if (vc) {{
    var counts = {{}};
    DATA.verdicts.forEach(function(v) {{ counts[v] = (counts[v]||0)+1; }});
    var labels = Object.keys(counts), values = Object.values(counts);
    var colors = {{'支持':'#00d2d3','部分支持':'#feca57','不支持':'#ff6b6b','无法判断':'#576574'}};
    var vctx = vc.getContext('2d');
    var W2 = vc.parentElement.clientWidth - 32, H2 = 260;
    vc.width = W2*2; vc.height = H2*2;
    vc.style.width = W2+'px'; vc.style.height = H2+'px';
    vctx.scale(2,2);
    var cx=W2/2, cy=H2/2-10, r=Math.min(cx,cy)-20, total=values.reduce(function(a,b){{return a+b}},0);
    var angle=0;
    values.forEach(function(v,i) {{
      var slice = v/total*Math.PI*2;
      vctx.fillStyle = colors[labels[i]] || '#576574';
      vctx.beginPath(); vctx.moveTo(cx,cy);
      vctx.arc(cx,cy,r,angle,angle+slice); vctx.closePath(); vctx.fill();
      var mid = angle+slice/2;
      var tx=cx+Math.cos(mid)*r*0.65, ty=cy+Math.sin(mid)*r*0.65;
      vctx.fillStyle='#0a0a0f'; vctx.font='bold 12px system-ui';
      vctx.fillText(v, tx-6, ty+4);
      angle += slice;
    }});
    // 图例
    var lx=20, ly=H2-15;
    labels.forEach(function(l,i) {{
      vctx.fillStyle = colors[l] || '#576574';
      vctx.fillRect(lx, ly-10, 10, 10);
      vctx.fillStyle = '#8395a7'; vctx.font = '10px system-ui';
      vctx.fillText(l + ' (' + values[i] + ')', lx+14, ly);
      lx += 70;
    }});
  }}
}})();
</script>
</body>
</html>"""

        if output_path:
            Path(output_path).write_text(html, encoding="utf-8")
            print(f"  可视化已保存: {output_path}")
            return output_path

        html_path = DATA_DIR / f"convergence_{int(time.time())}.html"
        html_path.write_text(html, encoding="utf-8")
        print(f"  可视化已保存: {html_path}")
        return str(html_path)

    def generate_hypothesis(self, query: str, previous_result: Optional[dict] = None) -> str:
        """从问题生成研究假设。如果有前一轮结果，基于反馈改善。"""
        if previous_result:
            system = f"""你是科学研究员。根据上一轮实验结果，调整假设。

上一轮结果:
- 最优G-score: {previous_result.get('best_G', '?')}
- 收敛状态: {previous_result.get('converged', False)}
- 关键发现: {previous_result.get('insight', '')}

请生成一个调整后的研究假设，用于下一轮模拟。
输出格式：一行，简洁的假设陈述。"""
            result = _llm_call(system, query, max_tokens=150)
        else:
            system = """你是科学研究员。根据用户问题，生成一个可验证的研究假设。
假设应该：
1. 明确、可测试
2. 包含预期结果方向
3. 与MMT/财政政策/经济模拟相关
输出格式：一行，简洁的假设陈述。"""
            result = _llm_call(system, query, max_tokens=150)

        return result.strip() if result else f"假设: {query[:100]}"

    def run_simulation_for_hypothesis(self, hypothesis: str, query: str) -> dict:
        """根据假设配置并运行模拟。"""
        # 从假设中提取关键参数方向
        # "高基建有利于控制通胀" → 提高 infra 权重
        sim = FiscalSimulator()
        sim.create_initial_population(8)

        # 根据假设调整初始种群的参数倾向
        if "高基建" in hypothesis or "基础设施" in hypothesis:
            for eco in sim.economies:
                eco.spending_infra = min(0.7, eco.spending_infra + 0.1)
        if "低税率" in hypothesis or "减税" in hypothesis:
            for eco in sim.economies:
                eco.tax_rate = max(0.1, eco.tax_rate - 0.05)
        if "高福利" in hypothesis or "福利" in hypothesis:
            for eco in sim.economies:
                eco.spending_welfare = min(0.6, eco.spending_welfare + 0.1)
        if "控制赤字" in hypothesis or "紧缩" in hypothesis:
            for eco in sim.economies:
                eco.deficit_ratio = max(0.0, eco.deficit_ratio - 0.03)

        # 运行模拟
        result = sim.evolution_cycle(rounds=15)

        # 提取关键指标
        survivors = result.get("survivors", [])
        best = result.get("best_policy", {})

        # ─── 模拟完整性自检 ───
        if sim.economies and len(sim.economies) > 0:
            eco = sim.economies[0]
            sim_params_check = {
                "deficit_ratio": getattr(eco, 'deficit_ratio', 0.05),
                "spending_infra": getattr(eco, 'spending_infra', 0.4),
                "spending_welfare": getattr(eco, 'spending_welfare', 0.3),
                "tax_rate": getattr(eco, 'tax_rate', 0.25),
                "kappa": getattr(eco, 'kappa', 0.5),
            }
        else:
            sim_params_check = {"deficit_ratio": 0.05, "spending_infra": 0.4, "spending_welfare": 0.3}
        
        sim_output = {
            "gdp": best.get("gdp", 0),
            "inflation": best.get("inflation", 0),
            "unemployment": best.get("unemployment", 0),
        }
        integrity = SimulationIntegrity.verify(sim_params_check, sim_output)
        if not integrity["passed"]:
            print(f"  ⚠ 模拟完整性警告: {integrity['summary']}")
            for v in integrity.get("violations", []):
                print(f"    {v.get('detail', '')}")

        # 计算改善幅度
        improvement_pct = 0
        if len(self.experiments) > 0:
            prev_best = self.experiments[-1].score
            curr_best = best.get("G_score", 0)
            if prev_best > 0:
                improvement_pct = round((curr_best - prev_best) / prev_best * 100, 1)

        return {
            "best_G": best.get("G_score", 0),
            "gdp": best.get("gdp", 0),
            "inflation": best.get("inflation", 0),
            "phi": best.get("phi", 0),
            "kappa": best.get("kappa", 0),
            "unemployment": best.get("unemployment", 0),
            "improvement_pct": improvement_pct,
            "survivors": [s["name"] for s in survivors],
            "full_result": result,
        }

    def verify_results(self, sim_result: dict, hypothesis: str, query: str) -> dict:
        """验证模拟结果是否符合假设。"""
        system = f"""你是研究验证员。判断模拟结果是否支持假设。

假设: {hypothesis}
结果: G={sim_result['best_G']}, GDP={sim_result['gdp']}, 通胀={sim_result['inflation']},
φ={sim_result['phi']}, κ={sim_result['kappa']}, 失业={sim_result['unemployment']}

请回答：
1. 假设是否得到支持？(支持/不支持/部分支持)
2. 主要发现（1-2句话）
3. 下一步改善方向（1句话）

输出格式（3行，不要序号）：
支持/不支持/部分支持
主要发现
改善方向"""

        result = _llm_call(system, query, max_tokens=200)
        if not result:
            return {"verdict": "无法判断", "finding": "", "improvement": ""}

        lines = result.strip().split("\n")
        return {
            "verdict": lines[0].strip() if len(lines) > 0 else "?",
            "finding": lines[1].strip() if len(lines) > 1 else "",
            "improvement": lines[2].strip() if len(lines) > 2 else "",
        }

    def check_convergence(self, scores: list[float]) -> bool:
        """检测G-score是否收敛（最近3轮波动<阈值）。"""
        if len(scores) < 3:
            return False
        recent = scores[-3:]
        avg = sum(recent) / len(recent)
        variance = sum((s - avg) ** 2 for s in recent) / len(recent)
        std = math.sqrt(variance)
        return std < self.convergence_threshold * max(avg, 0.01)

    def run_cycle(self, query: str, max_rounds: int = 5) -> dict:
        """
        执行完整的假设→模拟→验证→改善循环。
        
        返回包含所有轮次结果和最终建议的字典。
        """
        self.experiments = []
        self.best_score = 0.0
        previous_result = None
        all_scores = []

        print(f"\n{'='*60}")
        print(f"🔬 科学方法引擎启动 · 最多{max_rounds}轮")
        print(f"{'='*60}")

        for r in range(max_rounds):
            print(f"\n── 第{r+1}轮 ──")

            # ① 假设
            hypothesis = self.generate_hypothesis(query, previous_result)
            print(f"  假设: {hypothesis[:100]}")

            # ② 模拟
            sim_result = self.run_simulation_for_hypothesis(hypothesis, query)
            print(f"  模拟: G={sim_result['best_G']} GDP={sim_result['gdp']} "
                  f"通胀={sim_result['inflation']} φ={sim_result['phi']}")

            # ③ 验证
            verification = self.verify_results(sim_result, hypothesis, query)
            print(f"  验证: {verification['verdict']}")

            # ④ 改善
            improvement = verification.get("improvement", "")
            if not improvement:
                improvement = f"基于本轮结果调整参数方向 (G={sim_result['best_G']})"
            print(f"  改善: {improvement[:100]}")

            # 记录
            exp = Experiment(
                id=f"exp_{time.time()}_{r}",
                query=query,
                hypothesis=hypothesis,
                round_num=r + 1,
                sim_result=sim_result,
                verification=verification,
                improvement=improvement,
                score=sim_result["best_G"],
            )
            self.experiments.append(exp)
            all_scores.append(sim_result["best_G"])

            # 更新最佳
            if sim_result["best_G"] > self.best_score:
                self.best_score = sim_result["best_G"]
                self.best_result = sim_result

            # ⑤ 收敛检测
            if self.check_convergence(all_scores):
                exp.converged = True
                print(f"\n  ✅ 收敛! G-score 波动 < {self.convergence_threshold}")
                break

            # 准备下一轮
            previous_result = {
                "best_G": sim_result["best_G"],
                "converged": self.check_convergence(all_scores),
                "insight": verification.get("finding", ""),
            }

        # 生成最终报告
        final_report = self._generate_report(query)
        return final_report

    def _generate_report(self, query: str) -> dict:
        """生成最终研究报告。"""
        if not self.experiments:
            return {"error": "无实验数据"}

        # 提取演化轨迹
        trajectory = []
        for exp in self.experiments:
            trajectory.append({
                "round": exp.round_num,
                "hypothesis": exp.hypothesis[:100],
                "G_score": exp.score,
                "verdict": exp.verification.get("verdict", "?"),
                "converged": exp.converged,
            })

        # 计算改善幅度
        if len(trajectory) >= 2:
            first_score = trajectory[0]["G_score"]
            last_score = trajectory[-1]["G_score"]
            total_improvement = round((last_score - first_score) / max(first_score, 0.01) * 100, 1)
        else:
            total_improvement = 0

        # 最终假设
        final_hypothesis = self.experiments[-1].hypothesis
        final_verification = self.experiments[-1].verification

        # LLM生成综合结论
        summary_prompt = f"""根据以下科学方法循环的结果，生成研究结论：

原始问题: {query}
循环轮次: {len(trajectory)}轮
总改善: {total_improvement}%
收敛: {self.experiments[-1].converged}

演化轨迹:
{json.dumps(trajectory, ensure_ascii=False, indent=2)}

最终假设: {final_hypothesis}
验证: {final_verification.get('verdict')}
发现: {final_verification.get('finding')}

请生成：
1. 核心结论（1-2句）
2. 关键发现（3条要点）
3. 局限性和下一步建议"""

        conclusion = _llm_call(summary_prompt, query, max_tokens=400)

        return {
            "query": query,
            "method": "假设→模拟→验证→改善→循环",
            "rounds": len(self.experiments),
            "converged": self.experiments[-1].converged,
            "total_improvement_pct": total_improvement,
            "best_score": self.best_score,
            "trajectory": trajectory,
            "final_hypothesis": final_hypothesis,
            "final_verification": final_verification,
            "conclusion": conclusion or "研究完成",
            "best_result": self.best_result,
        }


# ════════════════════════════════════════════════════════
# 统一接口
# ════════════════════════════════════════════════════════

def scientific_research(query: str, max_rounds: int = 5) -> dict:
    """科学方法研究：假设→模拟→验证→改善→循环。"""
    engine = ScientificMethod(max_rounds=max_rounds)
    return engine.run_cycle(query, max_rounds=max_rounds)


def parameter_sweep(query: str, steps: int = 6, sim_name: str = "fiscal") -> dict:
    """参数敏感性扫描。"""
    engine = ScientificMethod()
    return engine.parameter_sweep(query, steps, sim_name)


def competing_hypotheses(query: str, num_hypotheses: int = 3, rounds_per: int = 2) -> dict:
    """竞争假说模式。"""
    engine = ScientificMethod()
    return engine.competing_hypotheses(query, num_hypotheses, rounds_per)


def render_convergence(path: Optional[str] = None) -> str:
    """生成收敛可视化HTML（需先运行run_cycle填充experiments）。"""
    engine = ScientificMethod()
    return engine.convergence_html(path)
if __name__ == "__main__":
    result = scientific_research("MMT框架下最优的赤字率和支出结构是什么", max_rounds=3)
    
    print(f"\n{'='*60}")
    print(f"研究完成 · {result['rounds']}轮 · 改善{result['total_improvement_pct']}%")
    print(f"收敛: {result['converged']}")
    print(f"\n演化轨迹:")
    for t in result["trajectory"]:
        print(f"  轮{t['round']}: G={t['G_score']} [{t['verdict']}] {t['hypothesis'][:60]}...")
    print(f"\n结论:\n{result['conclusion']}")
