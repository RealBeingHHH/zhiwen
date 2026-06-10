"""
表观遗传 — 同基因·不同表达

不改DNA序列。只改怎么读DNA。

甲基化标记落在操纵子的 operator_site 上:
  甲基化 → 抑制表达 (GGC↓ 模拟跳过)
  乙酰化 → 增强表达 (AAG↑ 搜索加深)
  磷酸化 → 调节表达 (CGT~ 验证减轻)

表达谱 (ExpressionProfile):
  学术深度模式:  GGC↑↑ CGT↑↑ TGC↑  AAG→  (重模拟·重验证·轻搜索)
  快速浏览模式:  AAG↑↑ GGC↓↓ CGT↓       (重搜索·轻模拟·轻验证)
  验证优先模式:  CGT↑↑↑ AAG→  GGC→     (重验证·正常搜索·正常模拟)
  默认模式:      无标记 (平衡表达)

用法:
  from epigenetics import EpigeneticRegulator, EXPRESSION_PROFILES
  regulator = EpigeneticRegulator()
  profile = EXPRESSION_PROFILES["academic_deep"]
  modified_operons = regulator.apply(operons, profile)
"""

import time, json, re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from enum import Enum

BASE = Path(__file__).parent
EPI_FILE = BASE / "data" / "epigenetic_state.json"
EPI_FILE.parent.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════════
# 表观标记类型
# ════════════════════════════════════════════════════════

class MarkType(Enum):
    METHYLATION = "methylation"        # 抑制 (CpG岛甲基化 → 基因沉默)
    ACETYLATION = "acetylation"        # 激活 (组蛋白乙酰化 → 染色质开放)
    PHOSPHORYLATION = "phosphorylation" # 调节 (磷酸化 → 活性调变)


@dataclass
class EpigeneticMark:
    """一个表观标记 = 对特定操纵子的甲基化/乙酰化/磷酸化。"""

    operon_name: str                   # 目标操纵子 (SEARCH/SIMULATE/VERIFY/CONTRAST)
    mark_type: MarkType                # 标记类型
    intensity: float = 0.0             # 强度 -1.0到+1.0 (负=抑制, 正=激活, 0=默认)
    reason: str = ""                   # 标记原因

    def apply(self, operon) -> None:
        """将标记应用到操纵子上。"""
        if self.mark_type == MarkType.METHYLATION:
            # 甲基化 → 抑制: 设置阻遏物
            if self.intensity < -0.3:
                operon.is_repressed = True
                operon.is_active = False
            elif self.intensity < -0.1:
                operon.is_active = False  # 轻度抑制

        elif self.mark_type == MarkType.ACETYLATION:
            # 乙酰化 → 激活: 清除阻遏, 提升优先级
            if self.intensity > 0.3:
                operon.is_repressed = False
                operon.is_active = True
                # 强激活: 复制密码子 (增强表达)
                if self.intensity > 0.6 and len(operon.codons) == 1:
                    # 单密码子操纵子 → 复制为2个 (双倍表达)
                    pass  # 保留为元标记, 由执行层处理

        elif self.mark_type == MarkType.PHOSPHORYLATION:
            # 磷酸化 → 调节: 减半强度
            if abs(self.intensity) > 0.2:
                # 调低密码子执行优先级
                pass


@dataclass
class ExpressionProfile:
    """一个表达谱 = 一组表观标记的集合。

    定义"在某种模式下, 哪些操纵子被激活/抑制"。
    """

    name: str                          # 谱名
    description: str                   # 描述
    marks: dict[str, EpigeneticMark]   # operon_name → mark
    priority: int = 0                  # 优先级 (多个谱匹配时选最高)

    # 触发条件
    trigger_signals: list[str] = field(default_factory=list)   # 触发关键词
    min_query_length: int = 0          # 最小查询长度
    max_depth: int = 5                 # 最大DAG深度


# ════════════════════════════════════════════════════════
# 预定义表达谱
# ════════════════════════════════════════════════════════

EXPRESSION_PROFILES: dict[str, ExpressionProfile] = {
    "academic_deep": ExpressionProfile(
        name="学术深度",
        description="重模拟·重验证·轻搜索。适合学术研究、论文分析。",
        marks={
            "SEARCH": EpigeneticMark("SEARCH", MarkType.METHYLATION, -0.1, "搜索不加深"),
            "SIMULATE": EpigeneticMark("SIMULATE", MarkType.ACETYLATION, 0.7, "模拟增强"),
            "VERIFY": EpigeneticMark("VERIFY", MarkType.ACETYLATION, 0.7, "验证增强"),
            "CONTRAST": EpigeneticMark("CONTRAST", MarkType.ACETYLATION, 0.5, "对比增强"),
        },
        trigger_signals=["研究", "分析", "论文", "学术", "证明", "验证", "深入"],
        min_query_length=10,
    ),

    "quick_scan": ExpressionProfile(
        name="快速浏览",
        description="重搜索·轻模拟·轻验证。适合快速了解、概览。",
        marks={
            "SEARCH": EpigeneticMark("SEARCH", MarkType.ACETYLATION, 0.6, "搜索增强"),
            "SIMULATE": EpigeneticMark("SIMULATE", MarkType.METHYLATION, -0.8, "模拟跳过"),
            "VERIFY": EpigeneticMark("VERIFY", MarkType.METHYLATION, -0.5, "验证减轻"),
            "CONTRAST": EpigeneticMark("CONTRAST", MarkType.METHYLATION, -0.3, "对比减轻"),
        },
        trigger_signals=["快速", "简单", "大概", "简述", "概述", "总结"],
        min_query_length=5,
        max_depth=1,
    ),

    "verify_heavy": ExpressionProfile(
        name="验证优先",
        description="重验证·正常搜索·正常模拟。适合数据核查、事实确认。",
        marks={
            "SEARCH": EpigeneticMark("SEARCH", MarkType.PHOSPHORYLATION, 0.0, "搜索正常"),
            "SIMULATE": EpigeneticMark("SIMULATE", MarkType.PHOSPHORYLATION, 0.0, "模拟正常"),
            "VERIFY": EpigeneticMark("VERIFY", MarkType.ACETYLATION, 0.9, "验证极强"),
            "CONTRAST": EpigeneticMark("CONTRAST", MarkType.ACETYLATION, 0.3, "对比增强"),
        },
        trigger_signals=["验证", "确认", "核实", "事实", "数据", "是否", "真的"],
        min_query_length=8,
    ),

    "creative_explore": ExpressionProfile(
        name="创意探索",
        description="重对比·重模拟·轻验证。适合头脑风暴、方案生成。",
        marks={
            "SEARCH": EpigeneticMark("SEARCH", MarkType.ACETYLATION, 0.4, "搜索广度↑"),
            "SIMULATE": EpigeneticMark("SIMULATE", MarkType.ACETYLATION, 0.6, "模拟增强"),
            "VERIFY": EpigeneticMark("VERIFY", MarkType.METHYLATION, -0.3, "验证减轻"),
            "CONTRAST": EpigeneticMark("CONTRAST", MarkType.ACETYLATION, 0.8, "对比极强"),
        },
        trigger_signals=["创意", "方案", "设计", "想法", "头脑风暴", "发散"],
        min_query_length=10,
    ),

    "default": ExpressionProfile(
        name="默认",
        description="平衡表达。无特殊标记。",
        marks={},
        trigger_signals=[],
    ),
}


# ════════════════════════════════════════════════════════
# 表观遗传调控器
# ════════════════════════════════════════════════════════

class EpigeneticRegulator:
    """表观遗传调控器 — 检测上下文 → 选择表达谱 → 应用标记。"""

    def __init__(self):
        self.current_profile: Optional[ExpressionProfile] = None
        self.history: list[dict] = []    # 表达谱切换历史
        self.user_profiles: dict[str, str] = {}  # user_id → profile_name
        self._load()

    def detect_profile(self, query: str, user_id: str = "",
                       context: dict = None) -> ExpressionProfile:
        """
        根据查询内容自动检测合适的表达谱。

        优先级:
          1. 用户指定的谱 (user_profiles)
          2. 触发关键词匹配
          3. 查询复杂度推断
          4. 默认谱
        """
        # 1. 用户指定
        if user_id and user_id in self.user_profiles:
            profile_name = self.user_profiles[user_id]
            profile = EXPRESSION_PROFILES.get(profile_name)
            if profile:
                self._record_switch(profile_name, "用户指定", query)
                return profile

        # 2. 关键词触发 (用匹配数评分, 选最高分)
        best_profile = None
        best_score = 0
        for name, profile in EXPRESSION_PROFILES.items():
            if name == "default":
                continue
            if len(query) < profile.min_query_length:
                continue
            matched = sum(
                1 for sig in profile.trigger_signals
                if sig in query
            )
            if matched > best_score:
                best_score = matched
                best_profile = (name, profile)

        if best_profile and best_score >= 1:
            name, profile = best_profile
            self._record_switch(name, f"触发词匹配({best_score}个)", query)
            return profile
        
        # 无触发词匹配 → 选第一个通过长度检测的谱作为备选
        if best_profile and best_score == 0:
            name, profile = best_profile
            # 无触发词时不强制用最佳匹配, 继续用复杂度推断

        # 3. 复杂度推断
        if len(query) > 100:
            self._record_switch("academic_deep", "长查询推断", query)
            return EXPRESSION_PROFILES["academic_deep"]
        elif len(query) < 15:
            self._record_switch("quick_scan", "短查询推断", query)
            return EXPRESSION_PROFILES["quick_scan"]

        # 4. 默认
        self._record_switch("default", "默认", query)
        return EXPRESSION_PROFILES["default"]

    def apply_profile(self, operons: list, profile: ExpressionProfile = None) -> list:
        """
        将表达谱应用到操纵子列表上。

        返回: 修改后的操纵子列表 (部分被抑制/激活)
        """
        if profile is None:
            profile = self.current_profile or EXPRESSION_PROFILES["default"]

        self.current_profile = profile

        modified = []
        for op in operons:
            mark = profile.marks.get(op.name)
            if mark:
                mark.apply(op)
            modified.append(op)

        return modified

    def set_user_profile(self, user_id: str, profile_name: str) -> bool:
        """为用户设置默认表达谱。"""
        if profile_name not in EXPRESSION_PROFILES:
            return False
        self.user_profiles[user_id] = profile_name
        self._save()
        return True

    def get_active_marks(self) -> list[dict]:
        """获取当前活跃的表观标记。"""
        if not self.current_profile:
            return []
        return [
            {
                "operon": name,
                "type": mark.mark_type.value,
                "intensity": mark.intensity,
                "reason": mark.reason,
            }
            for name, mark in self.current_profile.marks.items()
            if abs(mark.intensity) > 0.1
        ]

    def _record_switch(self, profile_name: str, reason: str, query: str):
        self.history.append({
            "timestamp": time.time(),
            "profile": profile_name,
            "reason": reason,
            "query_preview": query[:80],
        })
        if len(self.history) > 50:
            self.history = self.history[-50:]

    def _save(self):
        try:
            EPI_FILE.write_text(json.dumps({
                "user_profiles": self.user_profiles,
                "history": self.history[-20:],
            }, ensure_ascii=False, indent=2))
        except:
            pass

    def _load(self):
        try:
            if EPI_FILE.exists():
                data = json.loads(EPI_FILE.read_text())
                self.user_profiles = data.get("user_profiles", {})
                self.history = data.get("history", [])
        except:
            pass


# ════════════════════════════════════════════════════════
# 快捷接口
# ════════════════════════════════════════════════════════

def express_with_epigenetics(
    operons: list,
    query: str = "",
    user_id: str = "",
) -> list:
    """
    智能表达: 检测上下文 → 选择表达谱 → 应用到操纵子。

    返回: 修改后的操纵子列表
    """
    regulator = EpigeneticRegulator()
    profile = regulator.detect_profile(query, user_id)
    print(f"[表观遗传] 激活谱: {profile.name} ({profile.description})")
    print(f"[表观遗传] 标记: {regulator.get_active_marks()}")
    return regulator.apply_profile(operons, profile)


# ════════════════════════════════════════════════════════
# 操纵子数量调控 (基于表达谱)
# ════════════════════════════════════════════════════════

def adjust_operon_intensity(operons: list, profile: ExpressionProfile) -> list:
    """
    根据表达谱调整操纵子的"表达强度"。

    乙酰化(+) → 密码子复制 (双倍表达)
    甲基化(-) → 密码子跳过
    磷酸化(~) → 密码子减半

    返回: 调整后的密码子序列列表
    """
    adjusted = []

    for op in operons:
        mark = profile.marks.get(op.name)
        if not mark:
            adjusted.extend(op.codons)
            continue

        intensity = mark.intensity

        if intensity >= 0.6:
            # 强乙酰化 → 双倍表达
            adjusted.extend(op.codons * 2)
        elif intensity <= -0.6:
            # 强甲基化 → 全部跳过
            continue
        elif intensity <= -0.3:
            # 中度甲基化 → 只保留第一个密码子
            if op.codons:
                adjusted.append(op.codons[0])
        else:
            # 正常/轻度调节
            adjusted.extend(op.codons)

    return adjusted


# ═══ 自检 ═══
if __name__ == "__main__":
    from operon import detect_operons

    # 模拟操纵子
    test_codons = ["ATG", "AAG", "AAC", "GGC", "GGA", "CGT", "CGC", "TGC", "TAA"]
    operons = detect_operons(test_codons)

    print("=== 表观遗传测试 ===\n")

    for profile_name in ["academic_deep", "quick_scan", "default"]:
        profile = EXPRESSION_PROFILES[profile_name]
        print(f"[{profile.name}] {profile.description}")

        # 应用标记
        for op in operons:
            mark = profile.marks.get(op.name)
            if mark:
                op.is_repressed = False
                op.is_active = True
                mark.apply(op)

            status = "⊘抑制" if op.is_repressed else ("▶激活" if op.is_active else "·静默")
            intensity = profile.marks.get(op.name, EpigeneticMark("", MarkType.METHYLATION, 0)).intensity
            print(f"  {status} {op.name} [{intensity:+.1f}] {'·'.join(op.codons)}")

        # 密码子调整
        adjusted = adjust_operon_intensity(operons, profile)
        print(f"  密码子: {len(test_codons)} → {len(adjusted)} ({'+' if len(adjusted)>=len(test_codons) else ''}{len(adjusted)-len(test_codons)})\n")

    # 自动检测
    regulator = EpigeneticRegulator()
    print("=== 自动检测 ===")
    for query in ["深入研究日本MMT政策效果验证", "简单说说通胀", "验证这个数据是否真实"]:
        profile = regulator.detect_profile(query)
        print(f"  '{query[:30]}...' → {profile.name}")
