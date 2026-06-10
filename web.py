"""
了了之触 — 网络搜索模块
让了了能触碰外部世界的信息。

搜索后端 (按优先级):
- sogou: 搜狗搜索
- 360: 360搜索  
- baidu: 百度搜索
- duckduckgo: HTML 抓取 (无需 API key)
- deepseek: DeepSeek 知识后端 (final fallback)
"""

import json
import os
import re
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from typing import Optional

NETWORK_TIMEOUT = 5

# DeepSeek 训练数据截止日期
DEEPSEEK_CUTOFF = "2024年"


def extract_date_from_text(text: str) -> Optional[str]:
    """从文本中提取日期。返回 ISO 格式或 None。"""
    # 常见中文日期格式
    patterns = [
        (r'(\d{4})年(\d{1,2})月(\d{1,2})日', '{}-{:02d}-{:02d}'),  # 2025年3月15日
        (r'(\d{4})-(\d{2})-(\d{2})', '{}-{}-{}'),                   # 2025-03-15
        (r'(\d{4})/(\d{2})/(\d{2})', '{}-{}-{}'),                   # 2025/03/15
        (r'(\d{4})年(\d{1,2})月', '{}-{:02d}'),                     # 2025年3月
    ]
    for pat, fmt in patterns:
        m = re.search(pat, text)
        if m:
            try:
                groups = [int(g) for g in m.groups()]
                return fmt.format(*groups)
            except Exception:
                continue
    return None


def freshness_score(date_str: Optional[str]) -> str:
    """根据日期计算新鲜度标签。"""
    if not date_str:
        return "未知日期"
    try:
        # Try to parse the date
        if '-' in date_str:
            parts = date_str.split('-')
            d = datetime(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 1)
            now = datetime.now()
            age_days = (now - d).days

            if age_days < 7:
                return "本周"
            elif age_days < 30:
                return f"{age_days}天前"
            elif age_days < 365:
                return f"{age_days//30}个月前"
            else:
                return f"{date_str[:4]}年 (距今{age_days//365}年)"
    except Exception:
        pass
    return date_str


def search_web(query: str, max_results: int = 5) -> list:
    """搜索网络。多后端自动回退。"""
    # 1. 搜狗
    results = _search_sogou(query, max_results)
    if results:
        return results

    # 2. 360
    results = _search_360(query, max_results)
    if results:
        return results

    # 3. 百度
    results = _search_baidu(query, max_results)
    if results:
        return results

    # 4. DuckDuckGo
    results = _search_duckduckgo_html(query, max_results)
    if results:
        return results

    # 5. DeepSeek 知识 (终极回退)
    results = _search_deepseek_knowledge(query, max_results)
    return results


def _search_duckduckgo_html(query: str, max_results: int = 5) -> list:
    try:
        req = urllib.request.Request(
            f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}",
            headers={"User-Agent": "Liaoliao/2.0", "Accept": "text/html"},
        )
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    results = []
    link_pattern = re.compile(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
    snippet_pattern = re.compile(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
    links = link_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    for i, (href, title) in enumerate(links[:max_results]):
        title_clean = re.sub(r'<[^>]+>', '', title).strip()
        snippet_clean = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
        if title_clean and href.startswith("http"):
            results.append({"title": title_clean, "url": href, "snippet": snippet_clean[:300]})
    return results


def _search_baidu(query: str, max_results: int = 5) -> list:
    try:
        req = urllib.request.Request(
            f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}&rn={max_results}",
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36", "Accept-Language": "zh-CN,zh;q=0.9"},
        )
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    if "百度安全验证" in html:
        return []

    results = []
    h3_links = re.findall(r'<h3[^>]*>\s*<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
    if not h3_links:
        h3_links = re.findall(r'<a[^>]*data-showurl="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)
    if not h3_links:
        all_links = re.findall(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
        for href, text in all_links:
            clean = re.sub(r'<[^>]+>', '', text).strip()
            if any(d in href for d in ['baidu.com', 'bcebos.com', 'hao123.com']):
                continue
            if clean and 8 < len(clean) < 200:
                h3_links.append((href, clean))

    for href, title in h3_links[:max_results]:
        title_clean = re.sub(r'<[^>]+>', '', title).strip()
        title_clean = title_clean.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        if title_clean and len(title_clean) > 3 and not title_clean.startswith("http"):
            results.append({"title": title_clean[:150], "url": href, "snippet": ""})
    return results


def _search_deepseek_knowledge(query: str, max_results: int = 3) -> list:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("OPENAI_MODEL", "deepseek-chat")

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
        return []

    if "/chat/completions" not in base_url:
        base_url = base_url.rstrip("/") + "/chat/completions"

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是知识助手。根据训练数据简要回答用户问题，提供3个关键信息点。用中文。每条50字以内。格式：1. ...\n2. ...\n3. ..."},
            {"role": "user", "content": query},
        ],
        "temperature": 0.3,
        "max_tokens": 300,
    }

    try:
        req = urllib.request.Request(
            base_url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            results = []
            for line in content.strip().split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    clean = re.sub(r'^[\d\.\-\s]+', '', line).strip()
                    if clean:
                        results.append({"title": clean[:150], "url": "", "snippet": "(DeepSeek 知识)"})
            if not results:
                results.append({"title": content[:200], "url": "", "snippet": f"(DeepSeek 知识 · 数据截止{DEEPSEEK_CUTOFF})"})
            # 标注所有 DeepSeek 结果的数据截止日期
            for r in results:
                if "DeepSeek" in r.get("snippet", ""):
                    r["snippet"] = f"(DeepSeek 知识 · 数据截止{DEEPSEEK_CUTOFF} · 可能过时)"
            return results[:max_results]
    except Exception:
        return []


def fetch_page(url: str, max_chars: int = 3000) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Liaoliao/2.0", "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<head[^>]*>.*?</head>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def search_and_summarize(query: str) -> str:
    results = search_web(query, max_results=3)
    if not results:
        return ""
    parts = []
    for i, r in enumerate(results, 1):
        # 提取日期和新鲜度
        title_date = extract_date_from_text(r.get("title", ""))
        snippet_date = extract_date_from_text(r.get("snippet", ""))
        date_str = title_date or snippet_date
        fresh = freshness_score(date_str)

        parts.append(f"[{i}] {r['title']}")
        if fresh and fresh != "未知日期":
            parts.append(f"    📅 {fresh}")
        if r.get("snippet"):
            parts.append(f"    {r['snippet']}")
    return "\n".join(parts)


# ═══ 搜狗搜索 ═══
def _search_sogou(query: str, max_results: int = 5) -> list:
    """搜狗搜索。"""
    try:
        req = urllib.request.Request(
            f"https://www.sogou.com/web?query={urllib.parse.quote(query)}",
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36", "Accept-Language": "zh-CN,zh;q=0.9"},
        )
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    results = []
    # 搜狗: <h3><a href="URL">title</a></h3>
    h3_links = re.findall(r'<h3[^>]*>\s*<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
    for href, title in h3_links[:max_results]:
        title_clean = re.sub(r'<[^>]+>', '', title).strip()
        title_clean = title_clean.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        if title_clean and len(title_clean) > 5 and "搜狗" not in title_clean:
            # 尝试获取摘要
            snippet = ""
            snip_match = re.search(re.escape(href[:50]) + r'.{0,500}?class="[^"]*str_info[^"]*"[^>]*>(.*?)</', html, re.DOTALL)
            if snip_match:
                snippet = re.sub(r'<[^>]+>', '', snip_match.group(1)).strip()[:300]
            results.append({"title": title_clean[:150], "url": href, "snippet": snippet})
    return results


# ═══ 360搜索 ═══
def _search_360(query: str, max_results: int = 5) -> list:
    """360搜索。"""
    try:
        req = urllib.request.Request(
            f"https://www.so.com/s?q={urllib.parse.quote(query)}",
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36", "Accept-Language": "zh-CN,zh;q=0.9"},
        )
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    results = []
    # 360: <h3 class="res-title"><a href="URL">title</a>
    title_links = re.findall(
        r'<h3[^>]*class="[^"]*res-title[^"]*"[^>]*>.*?<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    )
    if not title_links:
        title_links = re.findall(
            r'<a[^>]*data-url="(https?://[^"]+)"[^>]*>(.*?)</a>',
            html, re.DOTALL,
        )

    # 获取摘要
    snippets = re.findall(r'<p[^>]*class="[^"]*res-desc[^"]*"[^>]*>(.*?)</p>', html, re.DOTALL)

    for i, (href, title) in enumerate(title_links[:max_results]):
        title_clean = re.sub(r'<[^>]+>', '', title).strip()
        title_clean = title_clean.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        if title_clean and len(title_clean) > 5:
            snippet = ""
            if i < len(snippets):
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()[:300]
            results.append({"title": title_clean[:150], "url": href, "snippet": snippet})
    return results
