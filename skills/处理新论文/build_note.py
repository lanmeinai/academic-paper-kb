#!/usr/bin/env python3
"""
build_note.py —— 根据 analyze_paper.py 的输出生成 Obsidian 笔记并更新索引。

用法:
  python skills/处理新论文/build_note.py <pdf_path> [--dry-run]

工作流:
  1. 读取 data/papers_processing_temp.json（DeepSeek 分析结果）
  2. 读取 data/index.json（已有论文库）
  3. 匹配参考文献中的库内论文，生成 WikiLink
  4. 生成 vault/论文笔记/<文件名>.md
  5. 更新主题索引、作者索引、index.json
  6. 移动 PDF 到对应分类目录
"""

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher

ROOT = Path(__file__).parent.parent.parent
INDEX_PATH = ROOT / "data" / "index.json"
TEMP_PATH = ROOT / "data" / "papers_processing_temp.json"
VAULT_NOTES = ROOT / "vault" / "论文笔记"
VAULT_TOPICS = ROOT / "vault" / "主题索引"
VAULT_AUTHORS = ROOT / "vault" / "作者索引"
PAPERS_DIR = ROOT / "papers"
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def load_index() -> dict:
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {"papers": [], "generated_at": ""}


def save_index(index: dict):
    index["generated_at"] = datetime.now().isoformat()
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def fuzzy_match(title: str, candidates: list[dict], threshold: float = 0.7) -> list[dict]:
    """模糊匹配标题，返回相似度 >= threshold 的候选论文列表。"""
    title_lower = title.lower().strip()
    matched = []
    for c in candidates:
        ct = (c.get("中文标题", "") or c.get("英文标题", "") or "").lower()
        ratio = SequenceMatcher(None, title_lower, ct).ratio()
        if ratio >= threshold:
            matched.append({**c, "_match_ratio": ratio})
    return sorted(matched, key=lambda x: -x["_match_ratio"])


def slugify(text: str) -> str:
    text = re.sub(r'[<>:"/\\|?*\']', '', text)
    text = re.sub(r'\s+', '_', text.strip())
    return text[:80]


def make_filename(paper: dict) -> str:
    year = paper.get("年份", 0) or 0
    authors = paper.get("作者列表", [])
    title_en = paper.get("英文标题", "") or paper.get("中文标题", "Unknown")

    first_author_last = ""
    if authors:
        parts = authors[0].strip().split()
        first_author_last = parts[-1] if parts else ""

    title_words = [w for w in re.sub(r'[^\w\s]', '', title_en).split()
                   if len(w) > 2 and w.lower() not in
                   ("the", "and", "for", "with", "using", "from", "based", "image",
                    "method", "study", "novel", "new", "via", "its")]
    title_short = "_".join(title_words[:5]) if title_words else "paper"

    return slugify(f"{year}_{first_author_last}_{title_short}")


def extract_year_from_text(text: str) -> int:
    """从论文文本中提取年份（回退方案）。"""
    patterns = [
        r'20(1[5-9]|2[0-6])\s*年',
        r'©\s*20(1[5-9]|2[0-6])',
        r'Published[:\s]*20(1[5-9]|2[0-6])',
        r'Accepted[:\s]*20(1[5-9]|2[0-6])',
        r'20(1[5-9]|2[0-6])\s*IEEE',
        r'20(1[5-9]|2[0-6])\s*Springer',
        r'20(1[5-9]|2[0-6])\s*ACM',
        r'20(1[5-9]|2[0-6])\s*Elsevier',
        r'arXiv:(\d{4})\.\d{5}',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            digits = re.findall(r'20(1[5-9]|2[0-6])', m.group(0))
            if digits:
                return int('20' + digits[0])
    return 0


def get_main_category(tags: list[str]) -> str:
    """根据标签动态确定主分类目录。

    优先使用 tag 本身作为分类目录名。如果 tag 不在默认列表中，
    使用第一个方法类/领域类的 tag。回退到 "其他"。
    """
    if not tags:
        return "其他"

    # 方法类关键词（更通用的分类维度）
    method_keywords = [
        "综述", "实验", "理论", "数值", "实证", "案例", "元分析",
        "方法论", "深度学习", "机器学习", "统计分析", "优化",
        "survey", "review", "experimental", "theoretical",
    ]

    # 优先选择可作为分类的标签
    for tag in tags:
        tag_lower = tag.lower()
        for kw in method_keywords:
            if kw.lower() in tag_lower:
                return tag

    # 回退：使用第一个标签作为分类
    return slugify(tags[0]) if tags[0] else "其他"


def render_note(paper: dict, ref_links: list[str]) -> str:
    tags = (paper.get("标签", []) or []) + (paper.get("自由标签", []) or [])
    tag_str = json.dumps(tags, ensure_ascii=False)
    authors_str = json.dumps(paper.get("作者列表", []), ensure_ascii=False)
    title_zh = paper.get("中文标题", "未命名")
    title_en = paper.get("英文标题", "")
    year = paper.get("年份", "???")
    journal = paper.get("发表期刊", "未知")
    pdf_path = paper.get("_pdf_path", "")

    # 标签链接
    tag_links = " · ".join(f"[[主题索引/{t}|{t}]]" for t in tags) if tags else "—"

    # 实验数据表格
    exp_rows = []
    for e in paper.get("实验数据", []) or []:
        exp_rows.append(
            f"| {e.get('数据集', '')} | {e.get('指标', '')} | {e.get('数值', '')} | {e.get('对比方法', '')} |"
        )
    exp_table = "\n".join(exp_rows) if exp_rows else "| — | — | — | — |"

    # 引用链接
    refs_section = "\n".join(f"- {r}" for r in ref_links) if ref_links else "_（未匹配到库内论文）_"

    lines = [
        "---",
        f'标题: "{title_zh}"',
        f'英文标题: "{title_en}"',
        f"作者: {authors_str}",
        f"年份: {year}",
        f"标签: {tag_str}",
        "引用数: 0",
        f'PDF路径: "{pdf_path}"',
        f'处理日期: "{datetime.now().strftime("%Y-%m-%d")}"',
        "---",
        "",
        f"# {title_zh}",
        "",
    ]
    if title_en and title_en != title_zh:
        lines.append(f"> *{title_en}*")
    authors_display = ", ".join(paper.get("作者列表", [])[:5])
    lines.append(f"> **{authors_display}** · {year}")
    lines.append("")

    lines.extend([
        "## 📋 基本信息",
        "",
        "| 项目 | 内容 |",
        "|------|------|",
        f"| 年份 | {year} |",
        f"| 作者 | {authors_display} |",
        f"| 发表期刊/会议 | {journal} |",
        f"| PDF | {pdf_path} |",
        "",
        "## 🏷️ 分类标签",
        "",
        tag_links,
        "",
        "## 📝 中文摘要",
        "",
        paper.get("中文摘要", "_暂无_") or "_暂无_",
        "",
        "## 💡 核心贡献",
        "",
        paper.get("核心贡献", "_暂无_") or "_暂无_",
        "",
        "## 🔬 方法概述",
        "",
        paper.get("方法概述", "_暂无_") or "_暂无_",
        "",
        "## 📊 实验数据摘录",
        "",
        "| 数据集 | 评估指标 | 数值 | 对比方法 |",
        "|--------|----------|------|----------|",
        exp_table,
        "",
        "## 🔗 引用了（库内论文）",
        "",
        refs_section,
        "",
        "## 📣 被以下论文引用",
        "",
        "_暂无_",
        "",
        "## 💭 我的笔记",
        "",
        "> ✏️ 在此手动记录阅读心得",
        "",
        "---",
    ])
    return "\n".join(lines)


def update_topic_index(tag: str, paper_info: dict, filename: str):
    """更新或创建主题索引页。"""
    tag_slug = slugify(tag)
    topic_file = VAULT_TOPICS / f"{tag_slug}.md"
    note_link = f"- [[论文笔记/{filename}|{paper_info.get('中文标题', filename)}]] （{paper_info.get('年份', '?')}）"

    if topic_file.exists():
        content = topic_file.read_text(encoding="utf-8")
        if note_link not in content:
            if "##" in content:
                idx = content.index("##")
                content = content[:idx] + note_link + "\n" + content[idx:]
            else:
                content += "\n" + note_link + "\n"
        count = content.count("- [[论文笔记/")
        content = re.sub(r'共 \d+ 篇论文', f'共 {count} 篇论文', content)
    else:
        content = f"""---
标签: "{tag}"
论文数: 1
---

# {tag}

共 1 篇论文

{note_link}

## 论文列表

{note_link}
"""
    topic_file.parent.mkdir(parents=True, exist_ok=True)
    topic_file.write_text(content, encoding="utf-8")


def update_author_index(author: str, paper_info: dict, filename: str):
    """更新或创建作者索引页。"""
    author_slug = slugify(author)
    author_file = VAULT_AUTHORS / f"{author_slug}.md"
    note_link = f"- [[论文笔记/{filename}|{paper_info.get('中文标题', filename)}]] （{paper_info.get('年份', '?')}）"

    if author_file.exists():
        content = author_file.read_text(encoding="utf-8")
        if note_link not in content:
            if "## 论文列表" in content:
                idx = content.index("## 论文列表")
                idx = content.index("\n", idx) + 1
                content = content[:idx] + note_link + "\n" + content[idx:]
            else:
                content += "\n" + note_link + "\n"
    else:
        content = f"""---
作者: "{author}"
论文数: 1
---

# 作者：{author}

## 论文列表

{note_link}
"""
    author_file.parent.mkdir(parents=True, exist_ok=True)
    author_file.write_text(content, encoding="utf-8")


def build(dry_run: bool = False):
    if not TEMP_PATH.exists():
        print("错误：找不到 data/papers_processing_temp.json")
        print("请先运行 analyze_paper.py")
        sys.exit(1)

    paper = json.loads(TEMP_PATH.read_text(encoding="utf-8"))
    if "error" in paper:
        print(f"分析出错: {paper['error']}")
        sys.exit(1)

    # 年份回退：如果 DeepSeek 未识别年份，从 PDF 文本中提取
    if (paper.get("年份", 0) or 0) == 0:
        text = paper.get("_full_text", "") or paper.get("中文摘要", "") or ""
        if not text:
            ext_path = ROOT / "data" / "_extract_temp.json"
            if ext_path.exists():
                try:
                    ext = json.loads(ext_path.read_text(encoding="utf-8"))
                    text = ext.get("full_text_preview", "")
                except Exception:
                    pass
        extracted_year = extract_year_from_text(text)
        if extracted_year > 0:
            paper["年份"] = extracted_year

    index = load_index()
    existing = index.get("papers", [])

    # 匹配参考文献
    ref_links = []
    ref_titles = paper.get("参考文献标题列表", []) or []
    for ref_title in ref_titles:
        matched = fuzzy_match(ref_title, existing)
        if matched:
            m = matched[0]
            m_title = m.get("中文标题") or m.get("英文标题", "")
            m_file = m.get("_filename", "")
            ref_links.append(f"[[论文笔记/{m_file}|{m_title}]]")

    # 生成文件名和分类
    filename = make_filename(paper)
    all_tags = (paper.get("标签", []) or []) + (paper.get("自由标签", []) or [])
    category = get_main_category(all_tags)

    # 生成笔记
    note = render_note(paper, ref_links)
    note_path = VAULT_NOTES / f"{filename}.md"

    if dry_run:
        print(f"[DRY RUN] 将生成: {note_path}")
        print(f"[DRY RUN] 分类: {category}")
        print(f"[DRY RUN] 引用匹配: {len(ref_links)} 篇")
        print(note[:500])
        return

    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(note, encoding="utf-8")

    # 移动 PDF
    src_pdf = paper.get("_pdf_path", "")
    if src_pdf and Path(src_pdf).exists():
        dest_dir = PAPERS_DIR / category
        dest_dir.mkdir(parents=True, exist_ok=True)
        pdf_name = f"{filename}.pdf"
        dest_path = dest_dir / pdf_name
        shutil.move(str(src_pdf), str(dest_path))
        paper["_pdf_path"] = str(dest_path.relative_to(ROOT)).replace("\\", "/")

    # 更新索引
    paper_entry = {
        "中文标题": paper.get("中文标题", ""),
        "英文标题": paper.get("英文标题", ""),
        "作者列表": paper.get("作者列表", []),
        "年份": paper.get("年份", 0),
        "标签": all_tags,
        "核心贡献": paper.get("核心贡献", ""),
        "_filename": filename,
        "pdf_path": paper.get("_pdf_path", ""),
        "处理日期": datetime.now().strftime("%Y-%m-%d"),
    }
    existing.append(paper_entry)
    save_index({"papers": existing})

    # 更新主题索引
    for tag in all_tags:
        update_topic_index(tag, paper_entry, filename)

    # 更新作者索引（仅前 3 位作者）
    for author in paper.get("作者列表", [])[:3]:
        update_author_index(author, paper_entry, filename)

    # 清理临时文件
    TEMP_PATH.unlink(missing_ok=True)

    print(f"[OK] 笔记已生成: {note_path}")
    print(f"[OK] 索引已更新: {len(existing)} 篇论文")
    print(f"[OK] 分类: {category}")
    print(f"[OK] 引用匹配: {len(ref_links)} 篇库内论文")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="生成 Obsidian 笔记并更新索引")
    parser.add_argument("pdf_path", nargs="?", help="原始 PDF 路径（用于移动）")
    parser.add_argument("--dry-run", action="store_true", help="预览不执行")
    args = parser.parse_args()

    # 将 PDF 路径写入临时数据
    if args.pdf_path:
        temp = json.loads(TEMP_PATH.read_text(encoding="utf-8")) if TEMP_PATH.exists() else {}
        temp["_pdf_path"] = args.pdf_path
        TEMP_PATH.write_text(json.dumps(temp, ensure_ascii=False, indent=2), encoding="utf-8")

    build(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
