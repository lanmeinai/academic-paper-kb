#!/usr/bin/env python3
"""
extract_pdf.py —— 从 PDF 提取全文文本和参考文献。

用法:
  python skills/处理新论文/extract_pdf.py "<pdf路径>"
  python skills/处理新论文/extract_pdf.py "<pdf路径>" --all-pages

输出 JSON 到 stdout:
  {"full_text_preview": "前3000字", "references_text": "参考文献部分原文", "total_pages": N}
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print(json.dumps({"error": "请先安装 PyMuPDF: pip install PyMuPDF"}, ensure_ascii=False))
    sys.exit(1)


def extract_pdf(pdf_path: str, all_pages: bool = False) -> dict:
    path = Path(pdf_path)
    if not path.exists():
        return {"error": f"文件不存在: {pdf_path}"}
    if path.suffix.lower() != ".pdf":
        return {"error": f"不是 PDF 文件: {pdf_path}"}

    doc = fitz.open(str(path))
    total_pages = doc.page_count

    if all_pages:
        full_text = []
        for page in doc:
            full_text.append(page.get_text())
        return {
            "full_text_preview": "\n\n".join(full_text)[:10000],
            "references_text": "",
            "total_pages": total_pages,
        }

    # 前 10 页：标题、摘要、方法
    front_pages = min(10, total_pages)
    front_text_parts = []
    for i in range(front_pages):
        front_text_parts.append(doc[i].get_text())

    # 后 5 页：参考文献
    back_pages = min(5, total_pages)
    back_text_parts = []
    if total_pages > front_pages:
        start = max(front_pages, total_pages - back_pages)
        for i in range(start, total_pages):
            back_text_parts.append(doc[i].get_text())

    doc.close()

    full_preview = "\n\n".join(front_text_parts)[:3000]
    refs_text = "\n\n".join(back_text_parts)

    return {
        "full_text_preview": full_preview,
        "references_text": refs_text,
        "total_pages": total_pages,
    }


def main():
    parser = argparse.ArgumentParser(description="从 PDF 提取文本")
    parser.add_argument("pdf_path", help="PDF 文件路径")
    parser.add_argument("--all-pages", action="store_true", help="提取全部页面")
    args = parser.parse_args()

    result = extract_pdf(args.pdf_path, all_pages=args.all_pages)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
