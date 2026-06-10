#!/usr/bin/env python3
"""
组件索引生成器 — 自动扫描了了模块地图与依赖关系

扫描 liaoliao/ 下所有 .py 文件，提取:
  - 公开API（类、函数、dataclass）
  - 模块docstring首行
  - 项目内部依赖关系（谁 import 了谁）
  - 按功能域分类

用法:
  python3 component_index.py            # 生成 data/component_index.json
  python3 component_index.py --text     # 打印可读文本
  python3 component_index.py --json     # 显式指定 JSON 输出
  python3 component_index.py -o <path>  # 自定义输出路径
"""

import ast
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional


# ════════════════════════════════════════════════════════════
# 配置
# ════════════════════════════════════════════════════════════

BASE = Path(__file__).parent  # liaoliao/ 目录
DATA_DIR = BASE / "data"
DEFAULT_OUTPUT = DATA_DIR / "component_index.json"

# 标准库模块名（Python 3.10+）
_STDLIB_MODULES = {
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio",
    "asyncore", "atexit", "audioop", "base64", "bdb", "binascii", "binhex",
    "bisect", "builtins", "bz2", "calendar", "cgi", "cgitb", "chunk",
    "cmath", "cmd", "code", "codecs", "codeop", "collections",
    "colorsys", "compileall", "concurrent", "configparser", "contextlib",
    "contextvars", "copy", "copyreg", "cProfile", "crypt", "csv",
    "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal",
    "difflib", "dis", "distutils", "doctest", "email", "encodings",
    "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput",
    "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt",
    "getpass", "gettext", "glob", "grp", "gzip", "hashlib", "heapq",
    "hmac", "html", "http", "idlelib", "imaplib", "imghdr", "imp",
    "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "keyword", "lib2to3", "linecache", "locale", "logging", "lzma",
    "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "multiprocessing", "netrc", "nis", "nntplib",
    "numbers", "operator", "optparse", "os", "ossaudiodev", "parser",
    "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil",
    "platform", "plistlib", "poplib", "posix", "posixpath", "pprint",
    "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr",
    "pydoc", "queue", "quopri", "random", "re", "readline",
    "reprlib", "resource", "rlcompleter", "runpy", "sched", "secrets",
    "select", "selectors", "shelve", "shlex", "shutil", "signal",
    "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver",
    "sqlite3", "ssl", "stat", "statistics", "string", "stringprep",
    "struct", "subprocess", "sunau", "symtable", "sys", "sysconfig",
    "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile",
    "termios", "test", "textwrap", "threading", "time", "timeit",
    "tkinter", "token", "tokenize", "trace", "traceback", "tracemalloc",
    "tty", "turtle", "turtledemo", "types", "typing", "unicodedata",
    "unittest", "urllib", "uu", "uuid", "venv", "warnings", "wave",
    "weakref", "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib",
    "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
    # 常用第三方（不在标准库但显然不是 liaoliao 内部）
    "fastapi", "uvicorn", "pydantic", "starlette",
    "numpy", "pandas", "requests", "httpx", "aiohttp",
    "PIL", "cv2", "torch", "tensorflow", "sklearn",
    "matplotlib", "plotly", "networkx", "scipy",
}


# ════════════════════════════════════════════════════════════
# 扫描器: 解析 Python 模块
# ════════════════════════════════════════════════════════════

def _get_module_name(filepath: Path) -> str:
    """从文件路径提取模块名（不含 .py）。"""
    return filepath.stem


def _first_docstring_line(node: ast.AST) -> Optional[str]:
    """提取 AST 节点中 docstring 的第一行（去除引号）。"""
    doc = ast.get_docstring(node)
    if not doc:
        return None
    lines = doc.strip().split("\n")
    first = lines[0].strip()
    # 去掉标题中的装饰符号但保留核心内容
    if len(first) > 80:
        first = first[:80] + "…"
    return first


def _is_liaoliao_module(name: str, all_py_files: set) -> bool:
    """判断 import 名称是否是 liaoliao 内部模块。"""
    # liaoliao 内部模块：顶层名恰好匹配某个 .py 文件名
    # 注意：有些模块可能有子模块，但我们只处理单文件模块
    top_level = name.split(".")[0]
    return top_level in all_py_files


def _resolve_import_name(name: str) -> str:
    """解析 import 名称，返回顶层模块名。"""
    return name.split(".")[0]


def scan_module(filepath: Path, all_modules: set) -> dict:
    """
    扫描单个 .py 文件，返回模块信息字典。

    返回:
        {
            "name": "module_name",
            "path": "module_name.py",
            "docstring": "第一行...",
            "public_classes": [...],
            "public_functions": [...],
            "public_vars": [...],
            "imports_from_liaoliao": [...],
            "imports_external": [...],
        }
    """
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return None

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    name = _get_module_name(filepath)
    result = {
        "name": name,
        "path": f"{name}.py",
        "docstring": _first_docstring_line(tree),
        "public_classes": [],
        "public_functions": [],
        "public_vars": [],
        "imports_from_liaoliao": [],
        "imports_external": [],
    }

    # ── 提取 import 语句 ──
    for node in ast.walk(tree):
        # import xxx, import xxx.yyy
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = _resolve_import_name(alias.name)
                if _is_liaoliao_module(top, all_modules):
                    if top not in result["imports_from_liaoliao"]:
                        result["imports_from_liaoliao"].append(top)
                else:
                    if top not in result["imports_external"] and top not in _STDLIB_MODULES:
                        result["imports_external"].append(top)

        # from xxx import yyy
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue  # 相对导入 from . import xxx — 不太可能出现
            top = _resolve_import_name(node.module)
            if _is_liaoliao_module(top, all_modules):
                if top not in result["imports_from_liaoliao"]:
                    result["imports_from_liaoliao"].append(top)
            else:
                if top not in result["imports_external"] and top not in _STDLIB_MODULES:
                    result["imports_external"].append(top)

    # ── 提取公开 API（module-level） ──
    for node in ast.iter_child_nodes(tree):
        # 类定义
        if isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                result["public_classes"].append({
                    "name": node.name,
                    "docstring": _first_docstring_line(node),
                })

        # 函数定义
        elif isinstance(node, ast.FunctionDef):
            if not node.name.startswith("_"):
                result["public_functions"].append({
                    "name": node.name,
                    "docstring": _first_docstring_line(node),
                })

        # 模块级赋值（常量/全局变量，非下划线开头）
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    # 只记录看起来像常量的（全大写）
                    if target.id.isupper() or target.id[0].isupper():
                        result["public_vars"].append({
                            "name": target.id,
                        })
                        break  # 每个赋值只记一次

    # 排序
    result["imports_from_liaoliao"].sort()
    result["imports_external"].sort()

    return result


# ════════════════════════════════════════════════════════════
# 依赖图
# ════════════════════════════════════════════════════════════

def build_dependency_graph(modules: list[dict]) -> dict:
    """
    构建依赖关系图。

    返回:
        {
            "module_a": {"imports": ["b", "c"], "imported_by": ["d", "e"]},
            ...
        }
    """
    graph = {}
    for mod in modules:
        graph[mod["name"]] = {
            "imports": mod["imports_from_liaoliao"],
            "imported_by": [],
        }

    # 反向计算 imported_by
    for mod_name, info in graph.items():
        for imported in info["imports"]:
            if imported in graph:
                graph[imported]["imported_by"].append(mod_name)

    # 排序
    for info in graph.values():
        info["imported_by"].sort()

    return graph


# ════════════════════════════════════════════════════════════
# 功能域分类
# ════════════════════════════════════════════════════════════

CATEGORIES = {
    "🧬 DNA架构": [
        "genome_core", "genome_pipeline", "genome_guardian",
        "knowledge_dna", "operon", "epigenetics", "dna_executor",
        "engineering_dag",
    ],
    "🔗 管线编排": [
        "pipeline", "server", "middleware", "route_fast",
        "deep_rounds", "cross_session",
    ],
    "🧠 深度研究": [
        "deep", "reasoning_engine", "research_planner",
        "evo_research", "hypothesis_pool", "pattern_memory",
        "adversarial", "feedback_loop", "self_audit",
    ],
    "🔬 科学方法": [
        "sci_method", "method_router", "causal_chain",
        "iterative_optimizer", "uncertainty", "fiscal_sim",
        "sim_adapter",
    ],
    "🌐 搜索与阅读": [
        "web", "special", "meta_search", "reader",
        "search_cache", "search_terms",
    ],
    "✅ 数据质量": [
        "data_gate", "relation_integrity",
    ],
    "📊 分析与可视化": [
        "analyze", "worldview", "worldview_contrast",
        "assurance_panel", "visual_panel", "cost_panel",
    ],
    "💾 知识存储": [
        "knowledge_graph", "matrix_store", "storage_manager",
        "session_learner",
    ],
    "⚖️ 权重与信任": [
        "niannian_weight", "tianshu_trust",
    ],
    "🪞 感知与追踪": [
        "eye", "trace", "cron_monitor",
    ],
    "🧵 核心组件": [
        "mind", "hand", "net", "soul", "engine",
    ],
    "🌉 桥接适配": [
        "voyager_auth", "voyager_bridge", "voyager_llm",
    ],
    "⚙️ 配置": [
        "config",
    ],
    "🧪 测试": [
        "test_pipeline", "end_to_end_test",
    ],
}


def classify_module(name: str) -> str:
    """返回模块所属的功能域。"""
    for cat, mods in CATEGORIES.items():
        if name in mods:
            return cat
    return "📦 其他"


# ════════════════════════════════════════════════════════════
# 主流程: 扫描 + 生成索引
# ════════════════════════════════════════════════════════════

def scan_all() -> dict:
    """扫描所有模块，返回完整索引字典。"""
    # 收集所有 .py 文件名（不含扩展名）
    py_files = sorted(BASE.glob("*.py"))
    all_module_names = {p.stem for p in py_files}

    modules = []
    for fp in py_files:
        if fp.name == "component_index.py":
            continue  # 跳过自身
        info = scan_module(fp, all_module_names)
        if info:
            modules.append(info)

    # 按名称排序
    modules.sort(key=lambda m: m["name"])

    # 构建依赖图
    dep_graph = build_dependency_graph(modules)

    # 分类
    by_category = defaultdict(list)
    for mod in modules:
        cat = classify_module(mod["name"])
        by_category[cat].append(mod["name"])

    # 统计
    total_modules = len(modules)
    total_classes = sum(len(m["public_classes"]) for m in modules)
    total_functions = sum(len(m["public_functions"]) for m in modules)
    total_imports = sum(len(m["imports_from_liaoliao"]) for m in modules)

    # 核心模块（被最多模块导入的，Top 10）
    core_modules = sorted(
        [(name, len(info["imported_by"])) for name, info in dep_graph.items() if info["imported_by"]],
        key=lambda x: -x[1]
    )[:10]

    # 孤立模块（既不 import 也不被 import）
    isolated = [
        name for name, info in dep_graph.items()
        if not info["imports"] and not info["imported_by"]
    ]

    index = {
        "meta": {
            "generated_by": "component_index.py",
            "total_modules": total_modules,
            "total_public_classes": total_classes,
            "total_public_functions": total_functions,
            "total_internal_imports": total_imports,
            "core_modules": [{"name": n, "imported_by_count": c} for n, c in core_modules],
            "isolated_modules": isolated,
        },
        "categories": {
            cat: {
                "modules": names,
                "count": len(names),
            }
            for cat, names in sorted(by_category.items())
        },
        "modules": modules,
        "dependency_graph": dep_graph,
    }

    return index


# ════════════════════════════════════════════════════════════
# 输出: JSON
# ════════════════════════════════════════════════════════════

def output_json(index: dict, path: Path) -> None:
    """输出 JSON 到文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"✅ 组件索引已生成: {path} ({path.stat().st_size:,} bytes)")


# ════════════════════════════════════════════════════════════
# 输出: 可读文本
# ════════════════════════════════════════════════════════════

def output_text(index: dict) -> str:
    """生成可读的文本报告。"""
    meta = index["meta"]
    lines = []

    # ── 头部 ──
    lines.append("╔══════════════════════════════════════════════════════════════╗")
    lines.append("║           了了 · 组件索引 · Component Index                  ║")
    lines.append("╠══════════════════════════════════════════════════════════════╣")
    lines.append(f"║  模块总数: {meta['total_modules']:<4}  公开类: {meta['total_public_classes']:<4}"
                 f"  公开函数: {meta['total_public_functions']:<4}  内部依赖: {meta['total_internal_imports']:<4} ║")
    lines.append("╚══════════════════════════════════════════════════════════════╝")
    lines.append("")

    # ── 核心模块 ──
    if meta["core_modules"]:
        lines.append("━━━ ★ 核心模块（被最多引用） ━━━")
        for i, cm in enumerate(meta["core_modules"], 1):
            bar = "█" * min(cm["imported_by_count"], 30)
            lines.append(f"  {i:>2}. {cm['name']:<25} ← {cm['imported_by_count']:>2} 个模块 {bar}")
        lines.append("")

    # ── 孤立模块 ──
    if meta["isolated_modules"]:
        lines.append("━━━ ∅ 孤立模块（无内部依赖） ━━━")
        lines.append("  " + ", ".join(meta["isolated_modules"]))
        lines.append("")

    # ── 按分类 ──
    for cat, cat_info in sorted(index["categories"].items()):
        lines.append(f"━━━ {cat}（{cat_info['count']} 模块） ━━━")
        for mod_name in cat_info["modules"]:
            mod = next(m for m in index["modules"] if m["name"] == mod_name)
            doc = mod.get("docstring") or "(无文档)"
            n_classes = len(mod["public_classes"])
            n_funcs = len(mod["public_functions"])
            n_imports = len(mod["imports_from_liaoliao"])

            # 模块摘要行
            parts = [f"  📄 {mod_name}.py"]
            if n_classes:
                parts.append(f"{n_classes}类")
            if n_funcs:
                parts.append(f"{n_funcs}函数")
            parts.append(f"→ {n_imports}依赖")
            lines.append("  ".join(parts))

            # Docstring 首行
            lines.append(f"      {doc}")

            # 公开类
            for cls in mod["public_classes"]:
                cls_doc = f" — {cls['docstring']}" if cls.get("docstring") else ""
                lines.append(f"      · class {cls['name']}{cls_doc}")

            # 公开函数
            for fn in mod["public_functions"]:
                fn_doc = f" — {fn['docstring']}" if fn.get("docstring") else ""
                lines.append(f"      · def {fn['name']}(){fn_doc}")

            # 依赖链
            if mod["imports_from_liaoliao"]:
                deps = " → ".join(mod["imports_from_liaoliao"][:6])
                if len(mod["imports_from_liaoliao"]) > 6:
                    deps += f" … (+{len(mod['imports_from_liaoliao']) - 6})"
                lines.append(f"      imports: {deps}")

            # 被谁依赖
            imported_by = index["dependency_graph"].get(mod_name, {}).get("imported_by", [])
            if imported_by:
                by_list = ", ".join(imported_by[:8])
                if len(imported_by) > 8:
                    by_list += f" … (+{len(imported_by) - 8})"
                lines.append(f"      imported_by: {by_list}")

            lines.append("")

    # ── 依赖关系矩阵（简化版） ──
    lines.append("━━━ 🔗 依赖关系矩阵 ━━━")
    lines.append("")
    dep_graph = index["dependency_graph"]
    # 只显示有依赖的模块
    connected = [(n, i) for n, i in dep_graph.items() if i["imports"] or i["imported_by"]]
    if connected:
        for mod_name, info in sorted(connected):
            if not info["imports"]:
                continue
            imp_str = " → ".join(info["imports"])
            lines.append(f"  {mod_name}")
            lines.append(f"    └─ imports: {imp_str}")
    else:
        lines.append("  (无内部依赖关系)")
    lines.append("")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════

def main():
    output_mode = "json"  # 默认 JSON
    output_path = DEFAULT_OUTPUT

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--text", "-t"):
            output_mode = "text"
        elif arg in ("--json", "-j"):
            output_mode = "json"
        elif arg in ("-o", "--output"):
            i += 1
            if i < len(args):
                output_path = Path(args[i])
        elif arg in ("-h", "--help"):
            print(__doc__)
            print("选项:")
            print("  --text, -t        输出可读文本")
            print("  --json, -j        输出 JSON（默认）")
            print("  -o, --output PATH 自定义输出路径")
            sys.exit(0)
        i += 1

    # 扫描
    print(f"🔍 扫描 liaoliao/ 目录 ...")
    index = scan_all()
    print(f"   找到 {index['meta']['total_modules']} 个模块, "
          f"{index['meta']['total_public_classes']} 个公开类, "
          f"{index['meta']['total_public_functions']} 个公开函数")

    if output_mode == "text":
        text = output_text(index)
        print(text)
        # 同时保存到文件
        txt_path = output_path.with_suffix(".txt")
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"✅ 文本报告已保存: {txt_path}")
    else:
        output_json(index, output_path)


if __name__ == "__main__":
    main()
