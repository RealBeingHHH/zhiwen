"""
了了之触 · 元搜索 — 自寻数据源

当常规搜索找不到数据时：
① LLM分析 → 推荐可能的数据源(URL/API)
② 逐源抓取 → 提取有效内容
③ 判断数据质量 → 返回或继续寻找
"""

import json
import os
import re
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional

from web import search_web, search_and_summarize, fetch_page, extract_date_from_text, freshness_score, DEEPSEEK_CUTOFF
from special import smart_search

TIMEOUT = 8


def _llm_call(system: str, user: str, max_tokens: int = 500) -> Optional[str]:
    """调用 DeepSeek API。"""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    # 用户必须在 .env 中配置。参见 .env.example 了解支持的供应商。
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("OPENAI_MODEL", "")

    env_file = os.path.join(os.path.dirname(__file__), ".env.llm")
    if (not api_key or len(api_key) < 20) and os.path.exists(env_file):
        try:
            with open(env_file) as f:
                env_vars = json.load(f)
            api_key = env_vars.get("OPENAI_API_KEY", "")
            base_url = env_vars.get("OPENAI_BASE_URL", base_url)
            model = env_vars.get("OPENAI_MODEL", model)
        except Exception:
            pass

    if not api_key or len(api_key) < 20:
        return None

    if "/chat/completions" not in base_url:
        base_url = base_url.rstrip("/") + "/chat/completions"

    body = {
        "model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.3, "max_tokens": max_tokens,
    }
    try:
        req = urllib.request.Request(base_url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
    except Exception:
        pass
    return None


def discover_sources(query: str) -> list:
    """
    LLM分析问题，推荐可能的数据源。
    返回: [{"url": "...", "description": "...", "why": "..."}, ...]
    """
    system = """你是数据源发现专家。用户需要某个数据但常规搜索引擎找不到。
请推荐3-5个可能包含该数据的网站URL或API端点。

输出格式（每行一个）：
URL | 简短描述 | 为什么推荐

示例：
输入: 中国最新GDP数据
输出:
https://data.stats.gov.cn | 国家统计局官网 | 官方GDP数据发布源
https://www.stats.gov.cn/sj/ | 统计局数据查询 | 直接数据入口
https://data.eastmoney.com/cjsj/gdp.html | 东方财富宏观数据 | 金融数据聚合"""

    result = _llm_call(system, query, max_tokens=400)
    if not result:
        return []

    sources = []
    for line in result.strip().split("\n"):
        line = line.strip()
        if not line or not line.startswith("http"):
            continue
        parts = line.split("|")
        if len(parts) >= 1:
            url = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else ""
            why = parts[2].strip() if len(parts) > 2 else ""
            if url.startswith("http"):
                sources.append({"url": url, "description": desc, "why": why})

    return sources[:5]


def smart_fetch(url: str, query: str) -> Optional[str]:
    """
    智能抓取：针对不同网站类型使用不同提取策略。
    返回提取到的有用文本，或 None。
    """
    # 常见API检测
    api_patterns = [
        (r'api\.', 'json'), (r'/api/', 'json'), (r'\.json', 'json'),
    ]
    is_api = any(re.search(p, url) for p, _ in api_patterns)

    if is_api:
        # Try JSON API
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Liaoliao/3.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = resp.read()
            try:
                parsed = json.loads(data)
                return json.dumps(parsed, ensure_ascii=False, indent=2)[:2000]
            except Exception:
                return data.decode("utf-8", errors="ignore")[:2000]
        except Exception:
            pass

    # HTML page fetch
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "text/html", "Accept-Language": "zh-CN,zh;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

    if len(html) < 500:
        return None

    # 提取有效文本
    # 移除 script/style/head
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<head[^>]*>.*?</head>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # 提取标题
    title = ""
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL)
    if title_match:
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

    # 提取正文（找最大的文本块）
    text = re.sub(r'<[^>]+>', '\n', html)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)

    # 分成段落，过滤掉太短的和导航文本
    paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 30]
    content = '\n\n'.join(paragraphs[:10])  # 最多10段

    if len(content) < 100:
        return None

    result = f"📄 {title}\n{content[:2000]}"
    return result


def quality_check(content: str, query: str) -> float:
    """判断抓取内容与查询的相关性。返回0-1分数。"""
    if not content:
        return 0.0

    # 简单关键词匹配
    keywords = [w for w in query if ord(w) > 127]  # 只取中文关键词
    if not keywords:
        keywords = query.split()

    matches = sum(1 for kw in keywords if kw in content)
    ratio = matches / max(1, len(keywords))
    length_score = min(1.0, len(content) / 500)
    return ratio * 0.7 + length_score * 0.3


def meta_search(query: str, max_sources: int = 4) -> dict:
    """
    元搜索：自寻数据源。
    
    流程:
    ① 常规搜索 → 有结果直接返回
    ② 无结果 → LLM发现数据源
    ③ 逐源抓取 → 质量检查
    ④ 返回最佳结果
    """
    t0 = time.time()
    result = {
        "query": query,
        "method": "常规搜索",
        "results": [],
        "sources_tried": [],
        "sources_found": 0,
        "time": 0,
    }

    # ── ① 常规搜索 ──
    # 专业API
    smart = smart_search(query)
    if smart and len(smart) > 50:
        result["results"].append({"source": "专业API", "content": smart, "quality": 1.0})
        result["time"] = round(time.time() - t0, 2)
        return result

    # 通用搜索
    summary = search_and_summarize(query)
    if summary and len(summary) > 80:
        result["results"].append({"source": "通用搜索", "content": summary, "quality": 0.8})
        result["time"] = round(time.time() - t0, 2)
        return result

    # ── ② LLM发现数据源 ──
    result["method"] = "自寻数据源"
    sources = discover_sources(query)
    if not sources:
        # DeepSeek兜底
        content = _llm_call(
            "你是知识助手。根据训练数据回答用户问题。如果不知道就说不知道。",
            query, max_tokens=300,
        )
        if content:
            result["results"].append({
                "source": f"LLM知识(截止{DEEPSEEK_CUTOFF})", 
                "content": content, "quality": 0.3,
            })
        result["time"] = round(time.time() - t0, 2)
        return result

    # ── ③ 逐源抓取 ──
    found_any = False
    for src in sources[:max_sources]:
        url = src["url"]
        result["sources_tried"].append(url)

        content = smart_fetch(url, query)
        if not content:
            continue

        quality = quality_check(content, query)
        if quality < 0.2:
            continue

        # 提取日期
        date_str = extract_date_from_text(content)
        fresh = freshness_score(date_str) if date_str else ""

        result["results"].append({
            "source": src.get("description", url),
            "url": url,
            "content": content[:1500],
            "quality": round(quality, 2),
            "date": fresh,
        })
        found_any = True

    result["sources_found"] = len(result["results"])

    # ── ④ 全无 → DeepSeek兜底 ──
    if not found_any:
        content = _llm_call(
            "你是知识助手。用户需要的数据所有来源都不可达。" +
            f"根据训练数据(截止{DEEPSEEK_CUTOFF})诚实回答。不知道就说不知道。",
            query, max_tokens=300,
        )
        if content:
            result["results"].append({
                "source": f"LLM知识(截止{DEEPSEEK_CUTOFF})",
                "content": content, "quality": 0.2,
            })

    result["time"] = round(time.time() - t0, 2)
    return result


def meta_search_to_context(query: str) -> str:
    """执行元搜索并格式化为LLM可用的上下文。"""
    mr = meta_search(query)
    if not mr["results"]:
        return ""

    parts = [f"[搜索方式: {mr['method']} · 尝试{mr['sources_found']}个源 · {mr['time']}s]"]
    for r in mr["results"]:
        date_tag = f" 📅{r['date']}" if r.get("date") else ""
        parts.append(f"\n【来源: {r['source']}{date_tag} · 质量{r['quality']}】\n{r['content'][:1200]}")
    return "\n".join(parts)


# ═══ 自检 ═══
if __name__ == "__main__":
    # 测试常规搜索
    for q in ["Python最新版本", "中国GDP 2025", "今天北京天气", "量子计算最新进展"]:
        print(f"\n{'='*50}")
        print(f"查询: {q}")
        result = meta_search(q)
        print(f"  方法: {result['method']} · {result['time']}s · {result['sources_found']}个结果")
        for r in result["results"]:
            print(f"  [{r['source'][:30]}] q={r['quality']:.2f} {r['content'][:100]}...")
