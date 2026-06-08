---
tags: [主页]
---

# 📚 学术论文知识库

## 快速导航

- [[主题索引/|🏷️ 按主题浏览]] — 按标签聚合的论文列表
- [[作者索引/|👤 按作者浏览]] — 按作者聚合的论文列表
- [[论文笔记/|📄 所有论文笔记]]

## 使用说明

1. 把 PDF 放入 `inbox/` 文件夹
2. 对 Claude Code 说「处理新论文」
3. 在此页面刷新后查看新增论文

> 💡 在 `config.json` 中设置你的研究领域，AI 分析会更精准。

## Dataview：最新处理的论文

```dataview
TABLE 年份, 标签, 核心贡献
FROM "论文笔记"
SORT 处理日期 DESC
LIMIT 10
```

## Dataview：按标签统计

```dataview
TABLE length(rows) AS 论文数量
FROM "论文笔记"
FLATTEN 标签
GROUP BY 标签
SORT length(rows) DESC
```
