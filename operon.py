"""
操纵子 (Operon) — 功能相关基因的聚合表达单元

细菌的发明: 功能相关基因物理相邻、单条mRNA、协同表达。
大腸桿菌 lac操纵子: 启动子→操纵子→lacZ→lacY→lacA→终止子
           吃了乳糖 → 阻遏蛋白脱落 → 三个酶同时转录

了了操纵子: 相关密码子聚合 → 并发执行 → 串行阻塞变为并行爆发

操纵子类型:
  [搜索操纵子]    AAG·AAC·AAT·AAA  → 四路搜索并发
  [验证操纵子]    CGT·CGC·CGA·CGG  → 四闸并行验证  
  [模拟操纵子]    GGC·GGA·GGG·GGT  → 多模拟并发
  [终止操纵子]    TAA·TAG·TGA      → 三终止协同
  [对比操纵子]    TGC·TGA·TGG      → 对比+对抗+迭代并发

结构:
  启动子(Promoter)  →  操纵基因(Operator)  →  结构基因(Structural Genes)
  各操纵子起始标记      调控位点(阻遏/激活)     密码子链(并发执行)

用法:
  from operon import Operon, OPERON_REGISTRY
  operon = Operon.detect(codons)     # 自动识别操纵子边界
  result = operon.express(context)   # 并发执行所有密码子
"""

import time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional


# ════════════════════════════════════════════════════════
# 操纵子结构
# ════════════════════════════════════════════════════════

@dataclass
class Operon:
    """一个操纵子 = 启动子 + 操纵基因 + 结构基因群。"""

    name: str                          # 操纵子名称
    codons: list[str]                  # 包含的密码子序列
    promoter: str = ""                 # 启动子 (识别标记)
    operator_site: str = ""            # 操纵基因 (调控位点)
    is_active: bool = True             # 是否激活 (阻遏蛋白状态)
    is_repressed: bool = False         # 被阻遏

    # 调控
    inducer: Optional[callable] = None     # 诱导物: 条件满足→激活
    repressor: Optional[callable] = None   # 阻遏物: 条件满足→抑制

    def evaluate(self, context: dict) -> bool:
        """评估操纵子是否应该表达。"""
        if self.repressor and self.repressor(context):
            self.is_repressed = True
            return False
        if self.inducer and not self.inducer(context):
            return False
        self.is_active = True
        return True

    def express(self, context: dict, executor: ThreadPoolExecutor = None) -> dict:
        """
        并发表达操纵子内的所有结构基因。

        每个密码子 → 独立的执行线程 → 所有结果聚合。

        返回: {codon_results, elapsed_ms, operon_name}
        """
        if not self.evaluate(context):
            return {
                "operon": self.name,
                "active": False,
                "repressed": self.is_repressed,
                "codons": self.codons,
                "results": [],
                "elapsed_ms": 0,
            }

        from dna_executor import execute_codon

        t0 = time.time()
        results = []

        if executor and len(self.codons) > 1:
            # 多密码子 → 线程池并发 (每个密码子最多8秒超时)
            futures = {}
            for codon in self.codons:
                future = executor.submit(execute_codon, codon, None, context)
                futures[future] = codon

            for future in as_completed(futures):
                codon = futures[future]
                try:
                    result = future.result(timeout=8)
                    result["codon"] = codon
                    results.append(result)
                except Exception as e:
                    results.append({
                        "codon": codon,
                        "action": "TIMEOUT",
                        "result": "error",
                        "error": "超时(%s)" % str(e)[:80],
                        "output": "",
                        "elapsed_ms": 8000,
                    })
        else:
            # 单密码子或无线程池 → 串行
            for codon in self.codons:
                result = execute_codon(codon, None, context)
                results.append(result)

        elapsed = int((time.time() - t0) * 1000)

        return {
            "operon": self.name,
            "active": True,
            "repressed": False,
            "codons": self.codons,
            "results": results,
            "elapsed_ms": elapsed,
        }


# ════════════════════════════════════════════════════════
# 操纵子注册表
# ════════════════════════════════════════════════════════

# 密码子前缀 → 操纵子类型映射
# A-系列 = 搜索族, C-系列 = 验证族, G-系列(非ATG) = 模拟族, T-系列(非STOP) = 对比族
CODON_FAMILIES = {
    "A": "SEARCH",    # AAG, AAC, AAT, AAA
    "C": "VERIFY",    # CGT, CGC, CGA, CGG, CAA
    "G": "SIMULATE",  # GGC, GGA, GGG, GGT (排除 ATG=START)
    "T": "CONTRAST",  # TGC, TGA, TGG (排除 TAA/TAG/TGA=STOP)
}

# 启动子标记: 每个操纵子族的第一个密码子
PROMOTERS = {
    "SEARCH":   "AAG",
    "VERIFY":   "CGT",
    "SIMULATE": "GGC",
    "CONTRAST": "TGC",
    "START":    "ATG",
    "STOP":     "TAA",
}


def detect_operons(codons: list[str]) -> list[Operon]:
    """
    从密码子序列中自动检测操纵子边界。

    规则:
      1. ATG 独自为 [START操纵子]
      2. 连续的 A-前缀密码子 → [SEARCH操纵子]
      3. 连续的 G-前缀密码子(非ATG) → [SIMULATE操纵子]
      4. 连续的 C-前缀密码子 → [VERIFY操纵子]
      5. 连续的 T-前缀密码子(非终止) → [CONTRAST操纵子]
      6. TAA/TAG/TGA → [STOP操纵子]
      7. 孤立的未知密码子 → 各自为 [PASS操纵子]
    """
    if not codons:
        return []

    operons = []
    i = 0

    while i < len(codons):
        codon = codons[i]
        prefix = codon[0] if codon else "?"

        # ATG = START (总是单独操纵子)
        if codon == "ATG":
            operons.append(Operon(
                name="START",
                codons=[codon],
                promoter="ATG",
            ))
            i += 1
            continue

        # TAA/TAG/TGA = STOP (聚合为终止操纵子)
        if codon in ("TAA", "TAG", "TGA"):
            stop_codons = []
            while i < len(codons) and codons[i] in ("TAA", "TAG", "TGA"):
                stop_codons.append(codons[i])
                i += 1
            operons.append(Operon(
                name="STOP",
                codons=stop_codons,
                promoter="TAA",
            ))
            continue

        # 按密码子前缀聚合
        family = CODON_FAMILIES.get(prefix, "PASS")

        if family == "PASS":
            operons.append(Operon(
                name="PASS",
                codons=[codon],
                promoter="?",
            ))
            i += 1
            continue

        # 聚合同族密码子
        family_codons = []
        while i < len(codons):
            c = codons[i]
            p = c[0] if c else "?"
            f = CODON_FAMILIES.get(p, "PASS")
            if f == family and c not in ("ATG", "TAA", "TAG", "TGA"):
                family_codons.append(c)
                i += 1
            else:
                break

        if family_codons:
            promoter = PROMOTERS.get(family, family_codons[0])
            operons.append(Operon(
                name=family,
                codons=family_codons,
                promoter=promoter,
            ))

    return operons


def express_operons(
    operons: list[Operon],
    context: dict,
    max_workers: int = 6,
) -> dict:
    """
    并发表达所有操纵子。

    操纵子之间串行 (保证数据依赖: START→SEARCH→SIMULATE→VERIFY→STOP)
    操纵子内部并发 (同族密码子并行执行)

    返回: {operon_results, total_elapsed_ms, ...}
    """
    t0 = time.time()
    operon_results = []
    collected = {
        "search_data": "",
        "simulation_result": "",
        "verification_result": None,
        "contrast_text": "",
        "adversarial_result": "",
        "panic_log": [],
    }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for operon in operons:
            # 每个操纵子并发表达内部密码子
            result = operon.express(context, executor=executor)
            operon_results.append(result)

            # 聚合收集的数据
            for r in result.get("results", []):
                output = r.get("output", "")
                action = r.get("action", "")
                if not output:
                    continue

                if action and action.startswith("SEARCH"):
                    collected["search_data"] += output + "\n"
                elif action and action.startswith("SIMULATE"):
                    collected["simulation_result"] += output + "\n"
                elif action and action.startswith("VERIFY"):
                    collected["verification_result"] = output
                elif action == "CONTRAST":
                    collected["contrast_text"] = output
                elif action == "ADVERSARIAL":
                    collected["adversarial_result"] = output

                if r.get("error"):
                    collected["panic_log"].append(
                        "[%s] %s" % (r.get("codon", "?"), r["error"][:80])
                    )

    elapsed = int((time.time() - t0) * 1000)

    return {
        "operon_results": operon_results,
        "collected": collected,
        "total_elapsed_ms": elapsed,
        "operon_count": len(operons),
        "parallel_operon_count": sum(1 for o in operons if len(o.codons) > 1),
    }


# ════════════════════════════════════════════════════════
# 快捷接口
# ════════════════════════════════════════════════════════

def execute_codons_with_operons(codons: list[str], context: dict) -> dict:
    """
    完整操纵子执行流程:
      1. 检测操纵子边界
      2. 并发表达各操纵子
      3. 返回聚合结果
    """
    operons = detect_operons(codons)
    result = express_operons(operons, context)
    result["operons"] = operons
    result["codons"] = codons

    # 汇总执行日志 (兼容旧格式)
    all_logs = []
    for op_result in result.get("operon_results", []):
        all_logs.extend(op_result.get("results", []))

    result["execution_log"] = all_logs
    result["actions_executed"] = [
        e.get("action", "?")
        for e in all_logs
        if e.get("result") == "ok"
    ]

    return result


# ════════════════════════════════════════════════════════
# 调控因子预定义 (供表观遗传层使用)
# ════════════════════════════════════════════════════════

def repressor_skip_simulation(ctx: dict) -> bool:
    """阻遏物: 如果查询不涉及科学领域，抑制模拟操纵子。"""
    try:
        from deep import _detect_scientific_domain
        return not _detect_scientific_domain(ctx.get("query", ""))
    except Exception:
        return True  # 默认抑制，安全


def repressor_no_search_data(ctx: dict) -> bool:
    """阻遏物: 如果已有搜索结果，跳过搜索。"""
    collected = ctx.get("collected", {})
    return bool(collected.get("search_data", "").strip())


def inducer_high_confidence(ctx: dict) -> bool:
    """诱导物: 管线结果可信度 > 0.7 时激活验证。"""
    pipeline_ctx = ctx.get("pipeline_ctx", {})
    gate = pipeline_ctx.get("gate_result")
    if gate and hasattr(gate, 'overall_score'):
        return gate.overall_score > 0.7
    return True  # 默认激活


# 调控因子注册表
REGULATORS = {
    "skip_simulation": repressor_skip_simulation,
    "no_search_data": repressor_no_search_data,
    "high_confidence": inducer_high_confidence,
}


# ═══ 自检 ═══
if __name__ == "__main__":
    # 测试操纵子检测
    test_codons = ["ATG", "AAG", "AAC", "GGC", "GGA", "CGT", "CGC", "TAA", "TGA"]
    operons = detect_operons(test_codons)

    print("=== 操纵子检测 ===")
    for op in operons:
        print("  %-12s 密码子: %s" % (op.name, " ".join(op.codons)))

    print("\n预期:")
    print("  START        [ATG]")
    print("  SEARCH       [AAG AAC]")
    print("  SIMULATE     [GGC GGA]")
    print("  VERIFY       [CGT CGC]")
    print("  STOP         [TAA TGA]")
