"""
了了之触 · 专业搜索 — 财经 · 热搜 · 学术 · 天气
"""

import json
import re
import urllib.request
import urllib.parse
from typing import Optional

TIMEOUT = 6


# ═══ 股票行情 ═══
def search_stock(query: str) -> dict:
    """查询股票行情。支持代码(000001/比亚迪)或名称。"""
    # 常见代码映射
    code_map = {
        "上证": "sh000001", "上证指数": "sh000001", "大盘": "sh000001",
        "深证": "sz399001", "深证成指": "sz399001",
        "创业板": "sz399006", "创业板指": "sz399006",
        "科创50": "sh000688", "沪深300": "sh000300",
        "比亚迪": "sz002594", "腾讯": "hk00700", "腾讯控股": "hk00700",
        "阿里巴巴": "hk09988", "阿里": "hk09988",
        "茅台": "sh600519", "贵州茅台": "sh600519",
        "宁德时代": "sz300750", "宁德": "sz300750",
        "中芯国际": "sh688981", "小米": "hk01810",
        "百度": "hk09888", "京东": "hk09618",
        "美团": "hk03690", "拼多多": "usPDD",
        "苹果": "usAAPL", "特斯拉": "usTSLA", "英伟达": "usNVDA",
        "微软": "usMSFT", "谷歌": "usGOOGL", "Meta": "usMETA",
    }

    # Parse query
    code = None
    q = query.strip().upper()

    # Direct code match
    code_match = re.match(r'^(\d{6})$', q.replace(" ", ""))
    if code_match:
        num = code_match.group(1)
        if num.startswith(("6", "0")):
            code = f"sh{num}"
        elif num.startswith(("3", "0")):
            code = f"sz{num}"
        else:
            code = f"sz{num}"

    # Name match
    if not code:
        for name, c in code_map.items():
            if name in query:
                code = c
                break

    if not code:
        return {"error": f"未找到「{query}」的股票代码，试试直接输入代码如 000001"}

    try:
        req = urllib.request.Request(
            f"https://qt.gtimg.cn/q={code}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read().decode("gbk", errors="ignore")
    except Exception as e:
        return {"error": f"获取行情失败: {e}"}

    for line in data.strip().split("\n"):
        if line.startswith("v_"):
            parts = line.split("~")
            if len(parts) < 40:
                continue
            return {
                "name": parts[1],
                "code": parts[2],
                "price": parts[3],           # 最新价
                "change": parts[31],          # 涨跌额
                "change_pct": parts[32],      # 涨跌幅%
                "high": parts[33],            # 最高
                "low": parts[34],             # 最低
                "open": parts[5],             # 今开
                "pre_close": parts[4],        # 昨收
                "volume": parts[6],           # 成交量
                "amount": parts[37],          # 成交额
                "time": parts[30],            # 时间
            }

    return {"error": f"未获取到 {code} 的数据"}


# ═══ 热搜 ═══
def search_trending(source: str = "weibo") -> list:
    """获取热搜榜。source: weibo/toutiao/baidu"""
    results = []

    if source == "weibo":
        try:
            req = urllib.request.Request(
                "https://weibo.com/ajax/side/hotSearch",
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://weibo.com"},
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                wb = json.loads(resp.read().decode("utf-8", errors="ignore"))
            for item in wb.get("data", {}).get("realtime", [])[:20]:
                word = item.get("word", "")
                rank = item.get("rank", "")
                if word:
                    results.append({"title": word, "rank": rank, "source": "微博热搜"})
        except Exception:
            pass

    if source == "toutiao" or (not results and source == "auto"):
        try:
            req = urllib.request.Request(
                "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            titles = re.findall(r'"Title":"([^"]+)"', html)
            for i, t in enumerate(titles[:20]):
                if t and len(t) > 3:
                    results.append({"title": t, "rank": str(i+1), "source": "头条热榜"})
        except Exception:
            pass

    if not results:
        try:
            req = urllib.request.Request(
                "https://top.baidu.com/board?tab=realtime",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            titles = re.findall(r'<div class="c-single-text-ellipsis">(.*?)</div>', html)
            for i, t in enumerate(titles[:20]):
                clean = re.sub(r'<[^>]+>', '', t).strip()
                if clean and len(clean) > 2:
                    results.append({"title": clean, "rank": str(i+1), "source": "百度热搜"})
        except Exception:
            pass

    return results


# ═══ 学术论文 ═══
def search_papers(query: str, max_results: int = 5) -> list:
    """搜索 arXiv 学术论文。"""
    results = []
    try:
        url = f"https://arxiv.org/search/?query={urllib.parse.quote(query)}&searchtype=all&start=0"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    # Parse results using arxiv ID + title pattern
    results_list = re.findall(
        r'arXiv:(\d+\.\d+).*?</a>.*?<p[^>]*>\s*(.*?)\s*</p>',
        html, re.DOTALL,
    )
    for arxiv_id, title in results_list[:max_results]:
        title_clean = re.sub(r'<[^>]+>', '', title).strip().replace('\n', ' ')[:200]
        if title_clean and len(title_clean) > 10 and "Showing" not in title_clean:
            results.append({
                "title": title_clean,
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "snippet": f"arXiv:{arxiv_id}",
            })

    return results


# ═══ 天气 ═══
def search_weather(city: str = "北京") -> dict:
    """查询天气。"""
    # 城市代码映射
    city_codes = {
        "北京": "101010100", "上海": "101020100", "广州": "101280101",
        "深圳": "101280601", "杭州": "101210101", "成都": "101270101",
        "武汉": "101200101", "南京": "101190101", "重庆": "101040100",
        "西安": "101110101", "长沙": "101250101", "天津": "101030100",
    }
    code = city_codes.get(city, "101010100")

    try:
        url = f"https://www.weather.com.cn/weather1d/{code}.shtml"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return {"error": f"天气查询失败: {e}"}

    # Extract weather info from hidden_title
    # Format: "06月09日20时 周二 多云 16/25°C"
    title_match = re.search(r'id="hidden_title" value="([^"]+)"', html)
    if title_match:
        text = title_match.group(1)
        # Parse: "06月09日20时 周二 多云 16/25°C"
        parts = text.split()
        if len(parts) >= 4:
            return {
                "city": city,
                "temperature": parts[3] if len(parts) > 3 else "?",
                "weather": parts[2] if len(parts) > 2 else "?",
                "wind": parts[4] if len(parts) > 4 else "",
                "date": f"{parts[0]} {parts[1]}" if len(parts) > 1 else "",
            }

    # Fallback: extract from JavaScript
    temp_match = re.search(r'(\d+)℃', html)
    wea_match = re.search(r'(\w+)\s+\d+\s*℃', html)
    if temp_match:
        return {
            "city": city,
            "temperature": temp_match.group(0),
            "weather": wea_match.group(1) if wea_match else "?",
            "wind": "?",
        }

    return {"error": "天气数据解析失败"}


# ═══ 统一路由 ═══
def smart_search(query: str) -> Optional[str]:
    """智能路由：根据查询内容选择专业后端，返回格式化结果。"""
    
    # 股票 — 仅在明确问价/行情时触发
    stock_keywords = ["股票", "股价", "涨跌", "行情", "市值", "上证", "深证", "创业板", "科创"]
    stock_names = ["比亚迪", "茅台", "宁德", "腾讯", "阿里", "特斯拉", "英伟达"]
    non_stock_keywords = ["技术", "车型", "电池", "销量", "对比", "优缺点", "自动驾驶", "系统", "芯片"]

    # 只有当包含"股价/行情"等词，或者单独问公司名+价格相关词时才走股票
    is_stock_query = any(k in query for k in stock_keywords)
    is_name_query = any(k in query for k in stock_names)
    is_non_stock = any(k in query for k in non_stock_keywords)

    if is_stock_query or (is_name_query and not is_non_stock):
        result = search_stock(query)
        if "error" not in result:
            return (
                f"📈 {result['name']}({result['code']})\n"
                f"最新价: {result['price']}  |  {result['change_pct']}%\n"
                f"今开: {result['open']}  |  最高: {result['high']}  |  最低: {result['low']}\n"
                f"昨收: {result['pre_close']}  |  成交额: {result['amount']}万"
            )
        return result.get("error", "")

    # 热搜
    if any(k in query for k in ["热搜", "热点", "热榜", "热门", "trending"]):
        source = "weibo"
        if "头条" in query: source = "toutiao"
        if "百度" in query: source = "baidu"
        results = search_trending(source)
        if results:
            lines = [f"🔥 {results[0].get('source', '热搜')}"]
            for r in results[:10]:
                lines.append(f"  {r['rank']}. {r['title']}")
            return "\n".join(lines)

    # 学术论文
    if any(k in query for k in ["论文", "paper", "学术", "arxiv", "arXiv", "研究"]):
        results = search_papers(query, 5)
        if results:
            lines = ["📚 arXiv 论文"]
            for r in results:
                lines.append(f"  • {r['title'][:120]}")
            return "\n".join(lines)

    # 天气
    if any(k in query for k in ["天气", "气温", "下雨", "刮风", "温度"]):
        cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "重庆", "西安", "长沙", "天津"]
        city = "北京"
        for c in cities:
            if c in query:
                city = c
                break
        result = search_weather(city)
        if "error" not in result:
            return f"🌤 {result['city']} {result['temperature']}℃ {result['weather']} {result['wind']}"

    # 百科/定义类查询
    if any(k in query for k in ["是什么", "什么是", "定义", "百科", "介绍", "版本", "最新"]):
        result = search_baike(query)
        if result:
            return result

    return None  # 走通用搜索


# ═══ 百度百科 ═══
def search_baike(query: str) -> Optional[str]:
    """搜索百度百科。"""
    import re as _re
    import urllib.parse
    keyword = _re.sub(r'(是什么|什么是|最新|版本|的定义)', '', query).strip()
    if not keyword or len(keyword) < 2:
        return None

    try:
        url = f"https://baike.baidu.com/item/{urllib.parse.quote(keyword)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

    if len(html) < 5000:
        return None

    # 提取摘要（"是一种" 附近的文本）
    idx = html.find("是一种")
    if idx < 0:
        idx = html.find("是指")
    if idx < 0:
        return None

    ctx = html[max(0, idx-100):idx+800]
    clean = _re.sub(r'<[^>]+>', ' ', ctx)
    clean = _re.sub(r'\s+', ' ', clean).strip()

    # 找最新版本
    version_info = ""
    ver_match = _re.search(r'最新[^。]{0,30}版本[^。]{0,50}', html)
    if not ver_match:
        ver_match = _re.search(r'稳定版本[^。]{0,50}', html)
    if ver_match:
        version_info = _re.sub(r'<[^>]+>', ' ', ver_match.group(0)).strip()
        version_info = _re.sub(r'\s+', ' ', version_info)

    result = f"📖 百度百科 · {keyword}\n{clean[:400]}"
    if version_info:
        result += f"\n\n📅 {version_info}"
    return result
