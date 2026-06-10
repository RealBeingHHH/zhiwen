"""
可视化解释面板 — 全层一屏可交互HTML仪表盘

将研究管线的所有层汇总到一个自包含的HTML页面:
  - 世界观选择 + 公理
  - 方法论路由 + 数据需求
  - 四层质量闸 (含织星φ+关系)
  - 不确定性σ
  - 因果追溯链
  - 对抗存活率
  - 综合置信度

数据通过内嵌JSON注入(smartFetch模式), 不依赖外部fetch。
"""

import json
import time
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent
DASHBOARD_DIR = BASE / "data" / "dashboards"
DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)


def build_dashboard_html(
    wv: dict,
    method: dict,
    gate_result,
    sigma: float = 0.0,
    adversarial_survival: float = 1.0,
    trace_weakest: str = "",
    query: str = "",
    output_path: Optional[str] = None,
) -> str:
    """生成自包含的可视化HTML面板。"""

    # 提取数据
    wv_name = wv.get("worldview_name", "未知")
    wv_axioms = wv.get("axioms", [])[:3]
    method_name = method.get("primary", "未知")
    gate_score = getattr(gate_result, "overall_score", 0)
    threshold = method.get("quality_threshold", 0.6)

    auth = gate_result.authenticity
    comp = gate_result.completeness
    acc = gate_result.accuracy
    ri = getattr(gate_result, "relation_integrity", {})

    data_json = json.dumps({
        "worldview": wv_name,
        "axioms": wv_axioms,
        "method": method_name,
        "gate": {
            "overall": gate_score,
            "threshold": threshold,
            "authenticity": auth.get("score", 0),
            "completeness": comp.get("score", 0),
            "accuracy": acc.get("score", 0),
            "relation": ri.get("score", 0) if isinstance(ri, dict) else 0,
        },
        "sigma": sigma,
        "adversarial_survival": adversarial_survival,
        "trace_weakest": trace_weakest,
        "query": query[:100],
    }, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>了了 · 研究保证面板</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#08080f;color:#c8d6e5;font-family:system-ui,sans-serif;padding:20px;min-height:100vh}}
h1{{font-size:16px;color:#48dbfb;margin-bottom:4px}}
.subtitle{{font-size:11px;color:#576574;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
.card{{background:#12121a;border:1px solid #1e1e2e;border-radius:12px;padding:16px}}
.card h3{{font-size:12px;color:#8395a7;margin-bottom:10px;text-transform:uppercase;letter-spacing:1px}}
.row{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.label{{font-size:11px;color:#576574}}
.value{{font-size:14px;font-weight:600}}
.good{{color:#00d2d3}}
.bad{{color:#ff6b6b}}
.warn{{color:#feca57}}
.bar-bg{{height:8px;background:#1e1e2e;border-radius:4px;overflow:hidden;margin:8px 0}}
.bar-fill{{height:100%;border-radius:4px;transition:width 0.5s}}
canvas{{width:100%;height:180px}}
.axiom{{font-size:11px;color:#8395a7;padding:4px 0;border-bottom:1px solid #1a1a24}}
.axiom:last-child{{border:none}}
.footer{{margin-top:24px;text-align:center;font-size:10px;color:#2d3436}}
</style>
</head>
<body>
<h1>🔍 了了 · 研究保证面板</h1>
<div class="subtitle" id="queryLine"></div>

<div class="grid" id="panel"></div>

<div class="footer">织星者体系 · τ天枢 φ织星 η玄鉴 · 全层可溯源</div>

<script>
var DATA = {data_json};

(function() {{
  document.getElementById('queryLine').textContent = '查询: ' + DATA.query;

  function bar(color, pct) {{
    return '<div class="bar-bg"><div class="bar-fill" style="width:' + (pct*100) + '%;background:' + color + '"></div></div>';
  }}

  function card(title, body) {{
    return '<div class="card"><h3>' + title + '</h3>' + body + '</div>';
  }}

  function row(label, value, cls) {{
    return '<div class="row"><span class="label">' + label + '</span><span class="value ' + (cls||'') + '">' + value + '</span></div>';
  }}

  var g = DATA.gate;
  var passed = g.overall >= g.threshold;

  // 世界观
  var wvBody = '<div style="font-size:14px;color:#48dbfb;margin-bottom:8px">' + DATA.worldview + '</div>';
  DATA.axioms.forEach(function(a) {{
    wvBody += '<div class="axiom">· ' + a + '</div>';
  }});
  wvBody += row('方法', DATA.method, 'good');

  // 质量闸
  var gateBody = row('综合', g.overall.toFixed(2) + ' / ' + g.threshold, passed?'good':'bad');
  gateBody += bar(passed?'#00d2d3':'#ff6b6b', g.overall);
  gateBody += row('① 真实性', g.authenticity.toFixed(1), g.authenticity>=0.6?'good':'warn');
  gateBody += row('② 完整性', g.completeness.toFixed(1), g.completeness>=0.6?'good':'warn');
  gateBody += row('③ 准确性', g.accuracy.toFixed(1), g.accuracy>=0.6?'good':(g.accuracy>=0.4?'warn':'bad'));
  gateBody += row('④ 关系', g.relation.toFixed(1), g.relation>=0.6?'good':'warn');

  // 不确定性
  var sigmaBody = '<div style="font-size:28px;text-align:center;color:' + (DATA.sigma<0.3?'#00d2d3':DATA.sigma<0.5?'#feca57':'#ff6b6b') + '">σ=' + DATA.sigma.toFixed(3) + '</div>';
  sigmaBody += '<div style="text-align:center;font-size:11px;color:#576574;margin-top:4px">不确定性</div>';
  sigmaBody += bar(DATA.sigma<0.3?'#00d2d3':DATA.sigma<0.5?'#feca57':'#ff6b6b', 1-DATA.sigma);

  // 对抗存活
  var advBody = '<div style="font-size:28px;text-align:center;color:' + (DATA.adversarial_survival>=0.75?'#00d2d3':DATA.adversarial_survival>=0.5?'#feca57':'#ff6b6b') + '">' + (DATA.adversarial_survival*100).toFixed(0) + '%</div>';
  advBody += '<div style="text-align:center;font-size:11px;color:#576574;margin-top:4px">对抗存活率</div>';

  // 追溯链最薄弱
  var traceBody = '<div style="font-size:12px;color:#feca57">⚡ ' + DATA.trace_weakest + '</div>';
  traceBody += '<div style="font-size:10px;color:#576574;margin-top:4px">因果追溯链最薄弱环节</div>';

  // 综合
  var confidence = passed ? (DATA.sigma<0.3 ? '🟢 高' : '🟡 中') : '🔴 低';
  var finalBody = '<div style="font-size:28px;text-align:center;margin-bottom:8px">' + confidence + '</div>';
  finalBody += row('质量闸', g.overall.toFixed(2), passed?'good':'bad');
  finalBody += row('σ', DATA.sigma.toFixed(3), DATA.sigma<0.3?'good':'warn');
  finalBody += row('对抗存活', (DATA.adversarial_survival*100).toFixed(0)+'%', DATA.adversarial_survival>=0.75?'good':'warn');

  document.getElementById('panel').innerHTML =
    card('🌌 世界观与公理', wvBody) +
    card('🔍 数据质量四闸', gateBody) +
    card('📊 不确定性 σ', sigmaBody) +
    card('⚔️ 对抗存活', advBody) +
    card('🔗 追溯链弱点', traceBody) +
    card('📐 综合判定', finalBody);
}})();
</script>
</body>
</html>"""

    if output_path:
        Path(output_path).write_text(html, encoding="utf-8")
        return output_path

    path = DASHBOARD_DIR / f"panel_{int(time.time())}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)


# ═══ 自检 ═══
if __name__ == "__main__":
    from data_gate import GateResult

    gate = GateResult()
    gate.overall_score = 0.58
    gate.authenticity = {"score": 0.65, "voyager_score": 0.61, "sources_found": 2}
    gate.completeness = {"score": 0.75}
    gate.accuracy = {"score": 0.60, "contradiction_count": 4}
    gate.relation_integrity = {"score": 0.50, "passed": 3, "failed": 1,
        "violations": [{"relation": "会计恒等式", "detail": "资产≠负债+权益"}]}

    wv = {"worldview_name": "法务实证",
          "axioms": ["所有可观测痕迹都是证据", "Benford定律不是巧合", "交叉验证>单一来源"]}
    method = {"primary": "forensic", "quality_threshold": 0.7}

    path = build_dashboard_html(
        wv, method, gate, sigma=0.45, adversarial_survival=0.67,
        trace_weakest="闸3 准确性=0.60",
        query="资产200亿，负债150亿，权益30亿。分析可信度",
        output_path=str(DASHBOARD_DIR / "test_dashboard.html"),
    )
    print(f"仪表盘: {path}")
