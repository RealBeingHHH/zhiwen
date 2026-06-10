"""
了了核心管线测试套件

覆盖: 世界观检测·方法路由·数据质量闸·关系完整性·TF-IDF·η权重·存储分层
运行: python3 test_pipeline.py
"""

import sys, json, time, math
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

passed = 0
failed = 0

def test(name):
    def decorator(fn):
        global passed, failed
        try:
            fn()
            passed += 1
            print(f"  ✅ {name}")
        except AssertionError as e:
            failed += 1
            print(f"  ❌ {name}: {e}")
        except Exception as e:
            failed += 1
            print(f"  💥 {name}: {type(e).__name__}: {e}")
        return fn
    return decorator


# ════════════════════════════════════════════════════════
# ① 世界观检测
# ════════════════════════════════════════════════════════

@test("世界观: MMT关键词检测")
def test_worldview_mmt():
    from worldview import WorldviewLayer
    result = WorldviewLayer.detect("MMT框架下最优赤字率是多少")
    assert result["worldview_key"] == "mmt", f"Expected mmt, got {result['worldview_key']}"

@test("世界观: 法务关键词检测")
def test_worldview_forensic():
    from worldview import WorldviewLayer
    result = WorldviewLayer.detect("某公司利润是否存在人为操纵和舞弊")
    assert result["worldview_key"] == "forensic", f"Expected forensic, got {result['worldview_key']}"

@test("世界观: 四神关键词检测")
def test_worldview_four_gods():
    from worldview import WorldviewLayer
    result = WorldviewLayer.detect("从天枢的视角看，这个数据可信吗")
    assert result["worldview_key"] == "four_gods"

@test("世界观: 闲聊回退四神")
def test_worldview_fallback():
    from worldview import WorldviewLayer
    result = WorldviewLayer.detect("今天天气真好")
    assert result["worldview_key"] == "four_gods"  # 默认回退


# ════════════════════════════════════════════════════════
# ② 方法论路由
# ════════════════════════════════════════════════════════

@test("方法路由: 优化→simulation")
def test_method_simulation():
    from method_router import MethodRouter
    result = MethodRouter.route("最优赤字率是多少，请模拟验证")
    assert result["primary"] == "simulation", f"Got {result['primary']}"

@test("方法路由: 定义→theoretical")
def test_method_theoretical():
    from method_router import MethodRouter
    result = MethodRouter.route("什么是MMT的核心定义")
    assert result["primary"] == "theoretical", f"Got {result['primary']}"

@test("方法路由: 对比→comparative")
def test_method_comparative():
    from method_router import MethodRouter
    result = MethodRouter.route("比较扩张性和紧缩性财政哪个更有效")
    assert result["primary"] == "comparative"

@test("方法路由: 默认→empirical")
def test_method_default():
    from method_router import MethodRouter
    result = MethodRouter.route("中国GDP是多少")
    assert result["primary"] == "empirical"


# ════════════════════════════════════════════════════════
# ③ 数据质量闸
# ════════════════════════════════════════════════════════

@test("数据闸: 空数据处理")
def test_gate_empty():
    from data_gate import DataGate
    result = DataGate.check("", ["统计数据"], 0.6, "test")
    assert result.blocked, "Empty data should be blocked"
    assert result.overall_score == 0.0

@test("数据闸: 正常数据通过")
def test_gate_normal():
    from data_gate import DataGate
    good_data = "2024年GDP 126万亿，消费48万亿，投资42万亿。来源: stats.gov.cn"
    result = DataGate.check(good_data, ["统计数据", "官方报告", "时效性数据"], 0.5, "GDP分析")
    assert result.overall_score > 0

@test("数据闸: 关系完整性检测")
def test_gate_relation():
    from data_gate import DataGate
    bad_data = "资产200亿，负债150亿，所有者权益30亿"
    result = DataGate.check(bad_data, ["原始账本"], 0.6, "财务分析")
    ri = result.relation_integrity
    assert ri is not None, "关系完整性检查应返回结果"


# ════════════════════════════════════════════════════════
# ④ 关系完整性
# ════════════════════════════════════════════════════════

@test("关系: Benford检测数字提取")
def test_relation_benford():
    from relation_integrity import RelationVerifier
    values = RelationVerifier.extract_key_values("GDP为126万亿，消费为48万亿")
    assert len(values) > 0, "应提取到数值"

@test("关系: 比率边界检测")
def test_relation_bounds():
    from relation_integrity import RelationVerifier
    result = RelationVerifier.verify("失业率-5%，通胀率2000%", worldview_key="forensic")
    violations = [v for v in result["violations"] if v["severity"] == "error"]
    assert len(violations) > 0, "应检测到比率边界违规"

@test("关系: τ有界性")
def test_relation_tau():
    from relation_integrity import RelationVerifier
    result = RelationVerifier.verify("τ = 1.5, φ = -0.3", worldview_key="four_gods")
    assert result["failed_count"] > 0, "应检测到τ超出边界"


# ════════════════════════════════════════════════════════
# ⑤ TF-IDF向量化
# ════════════════════════════════════════════════════════

@test("TF-IDF: 基本向量化")
def test_tfidf():
    from matrix_store import TFIDFVectorizer
    vec = TFIDFVectorizer()
    docs = ["最优赤字率为0.15", "会计等式断裂200≠180", "MMT主权货币理论"]
    vec.fit(docs)
    assert len(vec.vocabulary) > 0, "词汇表不应为空"
    
    vectors = vec.transform(["赤字率应该是多少"])
    assert len(vectors) == 1

@test("TF-IDF: 余弦相似度")
def test_tfidf_similarity():
    from matrix_store import TFIDFVectorizer
    vec = TFIDFVectorizer()
    docs = ["最优赤字率0.15通胀0.003", "会计等式200≠180", "天气真好"]
    vec.fit(docs)
    vectors = vec.transform(docs)
    
    query_vec = vec.transform(["赤字率"])[0]
    sims = vec.cosine_similarity(query_vec, vectors)
    assert sims[0] > sims[2], "赤字率查询应匹配赤字率文档而非天气"


# ════════════════════════════════════════════════════════
# ⑥ 念念η权重
# ════════════════════════════════════════════════════════

@test("η: 注视累加")
def test_eta_gaze():
    from niannian_weight import NiannianEta
    fid = "test_eta_fact_001"
    NiannianEta.gaze(fid, weight=1)
    NiannianEta.gaze(fid, weight=3)
    eta = NiannianEta.get_eta(fid)
    assert eta >= 5.0, f"两次注视后η应≥5, 实际{eta}"

@test("η: 排序功能")
def test_eta_ranking():
    from niannian_weight import NiannianEta
    f1 = {"node_id": "high_eta", "confidence": 0.7, "relevance": 0.8}
    f2 = {"node_id": "low_eta", "confidence": 0.7, "relevance": 0.8}
    NiannianEta.gaze("high_eta", weight=10)
    ranked = NiannianEta.rank_by_eta([f1, f2])
    assert ranked[0]["node_id"] == "high_eta", "高η应排前面"


# ════════════════════════════════════════════════════════
# ⑦ 存储分层
# ════════════════════════════════════════════════════════

@test("存储: 事实存取")
def test_storage_fact():
    from storage_manager import StorageManager
    nid = StorageManager.store_fact(
        "测试事实: 最优赤字率0.15", confidence=0.8,
        worldview="四神体系", method="simulation", gate_score=0.72, sigma=0.24,
    )
    assert nid, "存储应返回节点ID"
    
    facts = StorageManager.retrieve_facts("最优赤字率")
    assert len(facts) >= 1, "应检索到刚存储的事实"

@test("存储: 健康报告")
def test_storage_health():
    from storage_manager import StorageManager
    report = StorageManager.health_report()
    assert report["total_nodes"] > 0
    assert report["risk_level"] in ("healthy", "warning", "critical")


# ════════════════════════════════════════════════════════
# ⑧ 分层路由
# ════════════════════════════════════════════════════════

@test("路由: 闲聊→fast")
def test_route_fast():
    from route_fast import RouteLevel
    assert RouteLevel.detect("你好") == "fast"
    assert RouteLevel.detect("谢谢") == "fast"

@test("路由: 研究→deep")
def test_route_deep():
    from route_fast import RouteLevel
    assert RouteLevel.detect("对比MMT和新古典，分析最优赤字率策略") == "deep"

@test("路由: 事实→standard")
def test_route_standard():
    from route_fast import RouteLevel
    assert RouteLevel.detect("GDP是多少") == "standard"


# ════════════════════════════════════════════════════════
# ⑨ 不确定性量化
# ════════════════════════════════════════════════════════

@test("不确定性: 好数据σ低")
def test_uncertainty_good():
    from uncertainty import UncertaintyPropagator
    from data_gate import GateResult
    gate = GateResult()
    gate.authenticity = {"score": 0.85}
    gate.completeness = {"score": 0.80}
    gate.accuracy = {"score": 0.75}
    gate.relation_integrity = {"score": 0.70, "passed": 3, "failed": 0}
    bounds = UncertaintyPropagator.quantify(gate, has_simulation=False)
    assert bounds.sigma < 0.4, f"好数据σ应<0.4, 实际{bounds.sigma}"

@test("不确定性: 差数据σ高")
def test_uncertainty_bad():
    from uncertainty import UncertaintyPropagator
    from data_gate import GateResult
    gate = GateResult()
    gate.authenticity = {"score": 0.30}
    gate.completeness = {"score": 0.30}
    gate.accuracy = {"score": 0.20}
    gate.relation_integrity = {"score": 0.40, "passed": 0, "failed": 2}
    bounds = UncertaintyPropagator.quantify(gate, has_simulation=False)
    assert bounds.sigma > 0.5, f"差数据σ应>0.5, 实际{bounds.sigma}"


# ════════════════════════════════════════════════════════
# 运行
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    t0 = time.time()
    print(f"🧪 了了核心管线测试 ({len([k for k in dir() if k.startswith('test_')])} cases)\n")
    
    # All tests run via decorators above
    
    duration = time.time() - t0
    total = passed + failed
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed ({duration:.1f}s)")
    if failed:
        print(f"❌ {failed} FAILED")
        sys.exit(1)
    else:
        print(f"✅ ALL PASSED")
