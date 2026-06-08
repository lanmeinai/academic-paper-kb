#!/usr/bin/env python3
"""
analyze_paper.py —— 调用 DeepSeek API 分析论文内容。

用法:
  python skills/处理新论文/analyze_paper.py <extract_result.json>
  python skills/处理新论文/analyze_paper.py --stdin  # 从 stdin 读取 extract 输出

输出:
  data/papers_processing_temp.json   — DeepSeek 分析的结构化结果
"""

import json
import os
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print(json.dumps({"error": "请先安装 requests: pip install requests"}, ensure_ascii=False))
    sys.exit(1)

ROOT = Path(__file__).parent.parent.parent
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"


def load_config() -> dict:
    """加载用户配置。"""
    config_path = ROOT / "config.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def build_system_prompt() -> str:
    """根据用户配置构建领域感知的系统提示。"""
    config = load_config()
    domain = config.get("research_domain", "通用")
    domain_hint = config.get("domain_hint", "")

    base = f"""你是一位资深的学术论文分析专家。你的任务是从论文文本中提取结构化信息。

当前研究方向参考：{domain}
{"领域说明：" + domain_hint if domain_hint else ""}

要求：
1. 中文标题：如果原文有中文标题则使用原标题，否则将英文标题翻译为中文。专业术语使用该领域的标准译法
2. 中文摘要：用中文撰写200字以内的摘要，涵盖研究目的、方法、结果、结论
3. 核心贡献：用一句话概括本文最重要的学术贡献（50字以内）
4. 方法概述：3-5句话描述本文使用的核心方法
5. 标签：根据论文内容自动生成标签，从以下维度考虑：

标签体系：
- 方法类：论文使用的方法论特征（如：实验研究、理论分析、数值模拟、案例分析、实证研究、元分析等）
- 技术类：论文使用的具体技术（如：深度学习、统计分析、优化算法等），请根据论文实际内容确定
- 领域类：论文所属的研究领域和子领域
- 任务类：论文要解决的具体任务类型

6. 自由标签：根据论文特有内容添加1-3个补充标签
7. 实验数据：提取论文中报告的主要实验/评估结果（数据集/样本、评估指标、数值、对比方法）
8. 参考文献标题列表：从文本末尾提取所有被引用的论文标题（原文）

注意：
- 标签不要过于宽泛，要根据论文的实际内容精准标记
- 标签总数（含自由标签）建议 5-10 个
- 只返回 JSON，不要添加任何 markdown 代码块标记或额外解释。"""

    return base


def get_api_key() -> str:
    """从 .env 文件读取 DEEPSEEK_API_KEY。"""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        env_file = ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("DEEPSEEK_API_KEY"):
                    key = line.split("=", 1)[-1].strip().strip('"').strip("'")
                    break
    return key


def analyze(text_preview: str, refs_text: str) -> dict:
    api_key = get_api_key()
    if not api_key:
        return {"error": "未找到 DEEPSEEK_API_KEY，请在 .env 文件中设置"}

    system_prompt = build_system_prompt()

    user_prompt = f"""请分析以下学术论文的文本，提取结构化信息。

=== 论文正文（前10页） ===
{text_preview[:2500]}

=== 参考文献部分（后5页） ===
{refs_text[:2000] if refs_text else "（无参考文献文本）"}

请返回如下 JSON 格式（只返回 JSON，不要代码块标记）：
{{
  "中文标题": "",
  "英文标题": "",
  "作者列表": [],
  "年份": 0,
  "发表期刊": "",
  "中文摘要": "",
  "核心贡献": "",
  "方法概述": "",
  "标签": [],
  "自由标签": [],
  "实验数据": [
    {{"数据集": "", "指标": "", "数值": "", "对比方法": ""}}
  ],
  "参考文献标题列表": []
}}"""

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 4000,
                "temperature": 0.3,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()

        # 尝试提取 JSON（可能被 markdown 代码块包裹）
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            content = json_match.group(1).strip()

        result = json.loads(content)
        return result

    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析失败: {e}", "raw_response": content[:500] if 'content' in dir() else ""}
    except Exception as e:
        return {"error": str(e)}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--stdin":
        input_data = json.loads(sys.stdin.read())
    elif len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        if not input_path.exists():
            print(json.dumps({"error": f"文件不存在: {sys.argv[1]}"}, ensure_ascii=False))
            sys.exit(1)
        input_data = json.loads(input_path.read_text(encoding="utf-8"))
    else:
        print("用法: python analyze_paper.py <extract_result.json>")
        print("      python analyze_paper.py --stdin < extract_result.json")
        sys.exit(1)

    if "error" in input_data:
        print(json.dumps(input_data, ensure_ascii=False))
        sys.exit(1)

    result = analyze(
        input_data.get("full_text_preview", ""),
        input_data.get("references_text", ""),
    )

    # 写入临时文件
    out_path = ROOT / "data" / "papers_processing_temp.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
