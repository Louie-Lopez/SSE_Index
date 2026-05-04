---
name: got-mvp-full-run
description: 上证 GoT MVP 全流程：取数 → 快照 → Cursor 写 8 节点 JSON → run_mvp。
---

# GoT MVP 执行步骤（必要项）

约定：**`D`** = 快照日 `YYYY-MM-DD`，须与 `meta.json` 的 `snapshot_date`、`GOT_SNAPSHOT_DATE` / `run_mvp --snapshot-date` 一致。

## 1. 环境与依赖

```bash
python -m pip install -r requirements.txt
```

## 2. 取数（MCP，链外）

按 **`src/got_mvp/prompt_md/取数/MCP_宏观_EDB_取数.md`**、**`MCP_资讯_取数.md`** 调用 MCP，落盘到：

`src/got_mvp/data/snapshot_{D}/`

**必含文件**：`meta.json`、`CNMacroData.json`、`USMacroData.json`、`MacroNews.json`、`MesoNews.json`、`MicroNews.json`、`SSEIndex.json`（上证与宏观**分文件**）。

资讯 MCP 的 `time_start` / `time_end` 可与下式对齐（**可选**，取数前算窗）：

```bash
python -m src.got_mvp.support.cn_trading_days D
```

若多 query 资讯需合并去重，**按需**运行仓库内 `support/build_snapshot_news_dedupe_*.py`（若有对应日期脚本）。

## 3. 节点分析（Cursor，非 Python）

在 Cursor 中依次生成 **8 个** JSON，写入 **`{Agent父目录}/{D}/`**，文件名：`CNMacroData.json` … `CriticNode.json`。

- 系统说明：`src/got_mvp/prompt_md/节点/{同名}.md`
- 每步输入：该 `.md` 全文 + 本条事实 JSON（从 `snapshot_{D}/` 读；归并/决策/批判带上文已写好的节点摘要）
- 输出契约：每文件含 `report`（非空）、`evidence`（≥1 条）、`risk_flags`、`confidence`（0～1）；**`CriticNode`** 另含 `need_revision`（布尔）
- 顺序：**五路**（CN → US → Macro → Meso → Micro）→ **AggregateEvidence** → **DecisionNode**（可含同目录 `HumanInput_{D}.json`）→ **CriticNode**

勿覆盖 `HumanInput_{D}.json` 中已填写的人类正文，除非有意更新。

## 4. Python 运行顺序（主流程）

**只做一件事**：读快照 + 读 `{Agent父目录}/{D}/*.json` → 图编排 → 写 `src/got_mvp/data/evaluation/{D}/contradiction_evaluation.json` → stdout 打汇总 JSON。

```bash
python -m src.got_mvp.run_mvp --agent-dir <Agent父目录> --snapshot-date D
```

（未传 `--snapshot-date` 时用本机当天或环境变量 `GOT_SNAPSHOT_DATE`。）

**仅改人类/决策后重评**（五路与归并不改）：

```bash
python -m src.got_mvp.run_mvp --agent-dir <Agent父目录> --snapshot-date D --decision-only
```

首次带 Agent 目录跑时，若缺 `HumanInput_{D}.json`，主控会**新建占位**；已有文件不覆盖。

## 5. 结果位置

| 产物 | 路径 |
|------|------|
| 快照 | `src/got_mvp/data/snapshot_{D}/` |
| 节点 JSON | `{Agent父目录}/{D}/` |
| 矛盾粗检 | `src/got_mvp/data/evaluation/{D}/contradiction_evaluation.json` |

读盘校验失败时查 `src/got_mvp/nodes.py` 的 `_validate_agent_report`。
