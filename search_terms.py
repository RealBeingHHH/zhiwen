"""
专业搜索词映射 — 把通用数据需求翻译成高命中率的专业检索词

问题: "缺什么搜什么" → 低命中率
解决: 通用需求 → 专业术语 + 优先源 + 格式限定 → 精准检索

按世界观/方法论定制:
  - MMT: 部门平衡、功能性财政、就业保障 → 财政部/IMF/NBER
  - 新古典: 均衡、自然率、供给侧 → BIS/OECD/学术论文
  - 法务实证: 会计等式、Benford、审计 → cninfo/证监会/法院公告
  - 四神体系: τ源、φ涨落、η记录 → 天枢/织星/观测数据

专业词汇是搜索结果质量的钥匙。
"""

from typing import Optional


# ════════════════════════════════════════════════════════
# 数据需求 → 专业搜索词 + 优先源
# ════════════════════════════════════════════════════════

# 通用数据需求 → 跨领域的专业搜索词映射
REQUIREMENT_TO_TERMS = {
    # ── 统计数据类 ──
    "统计数据": {
        "default": ["统计年鉴", "年度数据", "同比 环比", "经济指标"],
        "mmt": ["部门平衡 政府赤字", "经常账户 GDP", "就业率 通胀率 2024"],
        "neoclassical": ["GDP 消费 投资 净出口 季度数据", "M2 利率 货币供应"],
        "forensic": ["财务比率 资产负债率", "行业均值 中位数", "利润率 周转率"],
        "four_gods": ["τ温度 信任指数", "φ涨落 间隔数据", "η记录 观测灵敏度"],
        "preferred_sites": ["stats.gov.cn", "data.stats.gov.cn", "imf.org"],
    },

    # ── 官方报告类 ──
    "官方报告": {
        "default": ["年度报告", "白皮书", "公报", "政府工作报告"],
        "mmt": ["财政部 决算报告", "央行 货币政策执行报告", "IMF fiscal monitor"],
        "neoclassical": ["世界经济展望 IMF", "OECD economic outlook", "世界银行 发展报告"],
        "forensic": ["审计报告 年报", "证监会 信息披露", "法院公告 破产清算"],
        "four_gods": ["天枢校准报告", "织星观测日志", "定倾守护记录"],
        "preferred_sites": ["gov.cn", "mof.gov.cn", "pbc.gov.cn", "cninfo.com.cn"],
    },

    # ── 学术论文类 ──
    "学术论文": {
        "default": ["学术论文 研究", "期刊 doi"],
        "mmt": ["现代货币理论 site:arxiv.org", "MMT functional finance site:ssrn.com",
               "就业保障 job guarantee site:nber.org"],
        "neoclassical": ["理性预期 均衡 site:arxiv.org", "DSGE 财政政策",
                         "natural rate unemployment site:nber.org"],
        "forensic": ["Benford law accounting", "financial statement fraud detection",
                     "earnings manipulation 实证"],
        "four_gods": ["信任锚定 天枢", "φ间隔 涌现", "观测者效应 复杂系统"],
        "preferred_sites": ["arxiv.org", "ssrn.com", "nber.org", "scholar.google.com", "cnki.net"],
    },

    # ── 时效性数据类 ──
    "时效性数据": {
        "default": ["最新 2025 2026", "今日 本周 本月"],
        "mmt": ["最新财政赤字 2025", "央行操作 最新", "国债收益率 最新"],
        "neoclassical": ["最新GDP 通胀 2025", "美联储 利率 最新", "PMI 最新"],
        "forensic": ["最新年报 2025", "最新审计意见", "最新 处罚 证监会"],
        "four_gods": ["天枢 最新校准", "织星 最新观测", "最新 τ温度"],
        "preferred_sites": ["eastmoney.com", "cninfo.com.cn", "reuters.com"],
    },

    # ── 财务报表类 ──
    "原始账本": {
        "default": ["资产负债表 利润表 现金流量表", "年报 年报 pdf"],
        "mmt": ["政府资产负债表 央行", "国家资产负债表 社科院"],
        "neoclassical": ["企业财务报表 上市公司", "行业财务数据"],
        "forensic": ["原始凭证 账簿", "银行流水 对账单", "纳税申报表"],
        "preferred_sites": ["cninfo.com.cn", "eastmoney.com", "sse.com.cn", "szse.cn"],
    },
    "企业财务报表": {
        "default": ["资产负债表 利润表 现金流量表 年报 pdf"],
        "preferred_sites": ["cninfo.com.cn", "eastmoney.com"],
    },

    # ── 审计类 ──
    "审计记录": {
        "default": ["审计报告 无保留意见", "内控审计", "会计师事务所"],
        "forensic": ["审计底稿", "审计调整分录", "关键审计事项"],
        "preferred_sites": ["cninfo.com.cn", "csrc.gov.cn", "cicpa.org.cn"],
    },
    "审计报告": {
        "default": ["审计报告 年度", "审计意见 持续经营"],
        "preferred_sites": ["cninfo.com.cn"],
    },

    # ── 行业数据类 ──
    "行业基准数据": {
        "default": ["行业平均 中位数", "行业报告 2024", "benchmark"],
        "forensic": ["同行业 上市公司 财务比率", "行业 利润率 均值 标准差"],
        "preferred_sites": ["eastmoney.com", "cninfo.com.cn", "stats.gov.cn"],
    },

    # ── 理论框架类 ──
    "定义": {
        "default": ["定义 概念", "是指 指的是", "含义 解释"],
        "mmt": ["现代货币理论 核心概念", "Chartalism 税收驱动货币", "功能性财政 定义"],
        "neoclassical": ["理性预期 定义", "市场出清 含义", "自然率假说"],
        "preferred_sites": ["wikipedia.org", "investopedia.com", "zhihu.com"],
    },
    "已有理论框架": {
        "default": ["理论框架 模型", "分析框架", "paradigm"],
        "mmt": ["部门平衡框架", "MMT 分析框架", "Kelton 赤字迷思"],
        "neoclassical": ["DSGE 框架", "新古典综合", "IS-LM 模型"],
        "four_gods": ["四神体系 公理", "天枢·织星·玄鉴·大圣", "φ η τ 框架"],
        "preferred_sites": ["arxiv.org", "ssrn.com"],
    },

    # ── 模拟类 ──
    "参数空间": {
        "default": ["参数 变量 因子", "系数 权重 参数空间"],
        "preferred_sites": [],
    },
    "初始条件": {
        "default": ["初始条件 基准 基线", "默认参数 假设条件"],
        "preferred_sites": [],
    },
    "历史校准数据": {
        "default": ["历史数据 校准", "时间序列 回溯 趋势"],
        "mmt": ["美国 赤字率 历史数据 1960-2024", "日本 国债 历史"],
        "neoclassical": ["GDP 历史数据 实际值", "利率 历史 时间序列"],
        "preferred_sites": ["fred.stlouisfed.org", "data.stats.gov.cn", "imf.org"],
    },

    # ── 对比类 ──
    "对照组数据": {
        "default": ["对照组 对比", "实验组 控制组", "基准组"],
        "preferred_sites": [],
    },
    "竞争性解释": {
        "default": ["争议 质疑", "相反观点 批评", "alternative explanation"],
        "preferred_sites": ["scholar.google.com", "arxiv.org"],
    },
    "差异指标": {
        "default": ["差异 差距 delta", "变化率 增长率 比较"],
        "preferred_sites": [],
    },

    # ── 综合类 ──
    "多源文献": {
        "default": ["综述 文献回顾", "meta-analysis", "研究综述"],
        "preferred_sites": ["scholar.google.com", "cnki.net", "arxiv.org"],
    },
    "历史脉络": {
        "default": ["历史演变 发展阶段", "时间线 大事记", "变迁"],
        "preferred_sites": [],
    },
    "不同视角": {
        "default": ["多角度 观点", "正反方 辩论", "争议 讨论"],
        "preferred_sites": [],
    },
}


# ════════════════════════════════════════════════════════
# 搜索词生成
# ════════════════════════════════════════════════════════

def build_search_query(
    missing_requirements: list[str],
    worldview_key: str = "",
    method_key: str = "",
    original_query: str = "",
) -> str:
    """
    将缺失的数据需求转换为高命中率的搜索查询。

    策略:
      1. 每个缺失需求 → 查找其专业搜索词映射
      2. 根据世界观/方法论选择最相关的术语
      3. 附加优先站点限定
      4. 将原始问题关键词混入以保持上下文相关性

    返回: 格式化后的搜索查询字符串
    """
    queries = []

    for req in missing_requirements:
        mapping = REQUIREMENT_TO_TERMS.get(req, {})
        if not mapping:
            # 无映射 → 使用原始需求词
            queries.append(req)
            continue

        # 选择与世界观最匹配的术语
        worldview_terms = mapping.get(worldview_key, [])
        default_terms = mapping.get("default", [])
        preferred_sites = mapping.get("preferred_sites", [])

        # 世界观特定术语优先，回退默认术语
        terms = worldview_terms if worldview_terms else default_terms

        if terms:
            # 取前3个最相关的术语
            selected_terms = terms[:3]
            term_str = " OR ".join(f'"{t}"' if " " in t else t for t in selected_terms)

            # 附加站点限定（取前2个优先站点）
            if preferred_sites:
                site_filters = " OR ".join(f"site:{s}" for s in preferred_sites[:2])
                query_part = f"({term_str}) ({site_filters})"
            else:
                query_part = f"({term_str})"

            queries.append(query_part)

    if not queries:
        return original_query

    # 混入原始问题的关键词（提取最关键的2-3个词）
    if original_query:
        # 简单提取: 去掉常见词, 取前20字中的关键词
        short = original_query[:80]
        queries.append(f'"{short}"')

    # 合并为最终查询
    return " ".join(queries)


def build_targeted_search_queries(
    missing_requirements: list[str],
    worldview_key: str = "",
    method_key: str = "",
    original_query: str = "",
) -> list[str]:
    """
    为每个缺失需求构建独立的、精确的搜索查询。
    返回多个查询（而非一个合并查询），适合逐条搜索。

    这样可以:
      - 每个查询都针对特定数据库，不会互相干扰
      - 如果某个查询没结果，其他的不受影响
      - 精确度远高于合并查询
    """
    targeted = []

    for req in missing_requirements:
        mapping = REQUIREMENT_TO_TERMS.get(req, {})
        if not mapping:
            targeted.append(req)
            continue

        worldview_terms = mapping.get(worldview_key, [])
        default_terms = mapping.get("default", [])
        preferred_sites = mapping.get("preferred_sites", [])

        terms = worldview_terms if worldview_terms else default_terms
        if not terms:
            targeted.append(req)
            continue

        # 每个需求生成多个专业查询（取前2个术语，每个单独查）
        for term in terms[:2]:
            query = term
            # 如果有优先站点，每个站点生成一个查询
            for site in preferred_sites[:2]:
                targeted.append(f"{query} site:{site}")
            if not preferred_sites:
                targeted.append(query)

        # 加入原始问题上下文
        if original_query:
            keywords = _extract_keywords(original_query)
            if keywords:
                targeted.append(f"{keywords} {terms[0]}")

    return targeted[:8]  # 最多8个查询


def _extract_keywords(text: str, max_words: int = 3) -> str:
    """从问题中提取关键词。"""
    # 去停用词
    stopwords = {"的", "是", "在", "了", "和", "吗", "呢", "什么", "怎么",
                 "为什么", "哪个", "如何", "可以", "应该", "需要", "这个",
                 "那个", "一个", "一下", "是否", "还是", "或者"}
    words = [w for w in text[:100].replace("？", "").replace("?", "").split()
             if w not in stopwords and len(w) > 1]
    return " ".join(words[:max_words])


# ═══ 自检 ═══
if __name__ == "__main__":
    test_cases = [
        (["官方报告", "学术论文", "时效性数据"], "mmt", "empirical", "MMT框架下赤字率对通胀的影响"),
        (["原始账本", "审计记录", "行业基准数据"], "forensic", "forensic", "某公司利润是否存在操纵"),
        (["统计数据", "定义", "已有理论框架"], "neoclassical", "theoretical", "理性预期下最优税率"),
    ]

    for missing, wv, method, query in test_cases:
        print(f"\n{'='*60}")
        print(f"缺失: {missing}")
        print(f"世界观: {wv} | 方法: {method}")
        print(f"原始问题: {query[:50]}...")
        print()

        # 合并查询
        combined = build_search_query(missing, wv, method, query)
        print(f"合并查询:")
        print(f"  {combined[:200]}")

        print()

        # 独立查询
        targeted = build_targeted_search_queries(missing, wv, method, query)
        print(f"独立查询 ({len(targeted)}条):")
        for i, t in enumerate(targeted):
            print(f"  [{i+1}] {t[:120]}")
