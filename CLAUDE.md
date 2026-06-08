# 学术论文知识库 - Claude Code 项目说明

## 项目用途
管理任意学术领域的论文 PDF，自动提取信息、分类存档、生成 Obsidian 笔记，辅助论文写作。

## 可用 Skill 列表

| 用户说 | 执行的 Skill | 说明 |
|--------|-------------|------|
| 「处理新论文」 | skills/处理新论文/SKILL.md | 处理 inbox/ 中的新 PDF |
| 「写论文辅助」 | skills/写论文辅助/SKILL.md | 生成 Related Work 框架 |
| 「导出参考文献」| skills/导出参考文献/SKILL.md | 导出 BibTeX 文件 |

## 执行任意 Skill 前必读
1. 先读取对应 SKILL.md 了解完整流程
2. API Key 从 .env 文件读取（DEEPSEEK_API_KEY）
3. 所有面向用户的输出内容使用中文

## 核心数据文件

### data/index.json 结构
每篇论文一条记录：
```json
{
  "文件名": "2023_Chen_A_novel_method.md",
  "中文标题": "一种新颖的方法",
  "英文标题": "A Novel Method for...",
  "作者列表": ["Chen, X.", "Wang, Y."],
  "年份": 2023,
  "发表期刊": "Nature",
  "标签": ["实验研究", "深度学习", "计算机视觉"],
  "自由标签": ["自监督学习"],
  "核心贡献": "提出了一种新颖的自监督学习框架",
  "PDF路径": "papers/实验研究/2023_Chen_A_novel_method.pdf",
  "笔记路径": "vault/论文笔记/2023_Chen_A_novel_method.md",
  "参考文献标题列表": ["ResNet: Deep Residual Learning...", "..."],
  "处理日期": "2025-01-01"
}
```

## 引用关系建立规则
- 从新论文的参考文献标题列表中，与 index.json 所有论文的英文标题做模糊匹配
- 相似度阈值 0.7（用 difflib.SequenceMatcher）
- 匹配成功则在新论文笔记中添加 [[WikiLink]]
- 同时在被引论文的笔记「被以下论文引用」部分追加反向链接

## DeepSeek API 调用规范
- 接口：https://api.deepseek.com/v1/chat/completions
- 模型：deepseek-chat
- 温度：0.3（保证输出稳定）
- 要求 AI 只返回 JSON，不含任何解释文字
- 解析前用正则去除 ```json ... ``` 包裹

## 领域适配
- 用户可在 config.json 中设置 `research_domain` 和 `domain_hint` 来适配特定领域
- AI 分析时会参考该配置生成更精准的标签和摘要
- 不设置则默认为"通用"，AI 自动识别论文领域
