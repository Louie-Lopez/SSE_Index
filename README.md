# GoT 宏观投资判断 MVP（Agent 文件模式）

**项目核心**：在某一 **交易日 D** 上，综合宏观、外溢与多层资讯，对 **上证综指走势作单日判断**（方向、尺度、置信与可证伪条件等），并与当日快照中的 **上证近端序列**对齐。

面向**第一次接触本仓库**的读者：上述判断由一条「多源数据 + 多节点报告 → 归并 → 决策 → 批判 → 程序化评估」的 **Graph of Thoughts (GoT) 最小闭环** 支撑。**不内置大模型调用**；各节点产出为磁盘上的 JSON，由你在 Cursor / 其它环境中按 `prompt_md` 生成后，用 **`run_mvp`** 读入、编排并输出汇总。

更偏方法与验收的说明见根目录 **[`GoT_MVP_说明书.md`](./GoT_MVP_说明书.md)**；批判与 MCP 局限等见 **[`待升级环节说明书.md`](./待升级环节说明书.md)**。

---

## 1. 本项目解决什么问题

- **问题定义**：给定 **交易日 D**，回答「**上证综指在该日语境下的短线走势判断**」（对标指数日度锚，非泛宏观综述）。
- **输入**：**D** 当日的「宏观 + 资讯」快照（MCP 取数落盘）与多份 **Agent 节点 JSON**（按 prompt 生成）。
- **输出**：上述 **单日判断** 的决策叙述（在 `DecisionNode.json` / 终端 JSON 的 `final_output` 中），以及**矛盾粗检**结果（落盘 `data/evaluation/{D}/contradiction_evaluation.json`）。
- **本仓库职责**：读快照、读 Agent 目录下的 JSON、（可选）LangGraph 编排、写评估结果、向 stdout 打印一次汇总 JSON。**取数在 MCP 侧完成**，规范见 `prompt_md/取数/` 下两份 md。

---

## 2. 架构鸟瞰

### 2.1 数据从哪来、到哪去

| 阶段 | 位置 | 说明 |
|------|------|------|
| 快照（原始输入） | `src/got_mvp/data/snapshot_{D}/` | `meta.json` + 五类业务块 JSON + **`SSEIndex.json`**（上证近端序列，**与 `CNMacroData.json` 分文件**）。由 **`snapshot_loader`** 读入 → `GoTState["snapshot_inputs"]`。资讯仅存「日期 + 标题」行，无正文片段。 |
| 节点产出（Agent） | `{GOT_AGENT_OUTPUT_DIR}/{D}/` | 8 个节点各一个 `{节点名}.json`；另有人类输入 **`HumanInput_{D}.json`**（见**第 5 节**）。 |
| 评估输出 | `src/got_mvp/data/evaluation/{D}/` | **`contradiction_evaluation.json`**：五路 `evidence` 与「归并+决策」叙述的程序化对照（方法见文件内 `method_note`）。 |

### 2.2 图结构（与 `graph.py` 一致）

五路输入在工程上为 **串行边**（便于按顺序读 JSON），语义上仍为五视角独立分析 → **`AggregateEvidence`** 归并 → **`DecisionNode`** 输出 **D 日上证单日判断**（可含人类输入）→ **`CriticNode`** 批判；条件边上 **`need_revision`** 时最多回流 **1** 次到归并。从 Agent 目录读盘时设 **`skip_revision_loop`**，不自动多轮回流。

---

## 3. 目录与重要文件

| 路径 | 作用 |
|------|------|
| `src/got_mvp/prompt_md/节点/*.md` | 各节点给 Agent 的系统说明与 JSON 字段约定。 |
| `src/got_mvp/prompt_md/节点/HumanInput.md` | 人类输入文件名、占位规则、与 `--decision-only` 的配合。 |
| `src/got_mvp/prompt_md/取数/` | MCP 宏观 EDB、资讯取数字段与时间窗约定。 |
| `src/got_mvp/run_mvp.py` | 命令行入口。 |
| `src/got_mvp/graph.py` | 初始状态、LangGraph 或顺序执行、**`--decision-only`** 分支。 |
| `src/got_mvp/nodes.py` | 读盘校验各节点 JSON。 |
| `src/got_mvp/evaluation.py` | 矛盾粗检与写 `data/evaluation/`。 |
| `src/got_mvp/support/` | `snapshot_loader`、`node_output_json`（含 **`HumanInput_{D}.json`** 占位）、`cn_trading_days` 等。 |

---

## 4. 节点与 JSON 契约（读盘时校验）

每个节点一个 JSON，**必填**：**`report`**、**`evidence`**（字符串数组，至少一条）、**`risk_flags`**、**`confidence`**（0～1）。**`CriticNode`** 另可选 **`need_revision`**。详细写法见对应 **`prompt_md/节点/{节点名}.md`**。

节点名与文件：`CNMacroData`、`USMacroData`、`MacroNews`、`MesoNews`、`MicroNews`、`AggregateEvidence`、`DecisionNode`、`CriticNode`。

---

## 5. 人类输入 `HumanInput_{D}.json`

- **路径**：与上述节点 JSON 同级，`D` 与 **`GOT_SNAPSHOT_DATE` / `--snapshot-date`** 一致，例如 `HumanInput_2026-05-03.json`。
- **生成**：首次带有效 Agent 目录跑 **`run_mvp`** 时，主控若发现该文件不存在，会写入**占位**；**已存在则绝不覆盖**。
- **使用**：人类编辑 **`human_note`**（及可选 **`evidence`**）；若 **`human_note` 与 `evidence` 皆空**，主控视为本轮**未使用**人类输入。
- **全流程后再改决策**：五路与归并已定型时，只需改 **`HumanInput_{D}.json`** 和/或 **`DecisionNode.json`**，然后：

```text
python -m src.got_mvp.run_mvp --agent-dir 父目录 --snapshot-date D --decision-only
```

（或 **`GOT_DECISION_ONLY=1`**。）仍顺序读盘五路→归并→决策→批判并刷新评估；**不经 LangGraph 批判回流**。终端 JSON 中 **`observability.decision_only`** 为 `true`。

---

## 6. 环境与命令

### 6.1 依赖安装

```bash
python -m pip install -r requirements.txt
```

`chinesecalendar` 用于 `python -m src.got_mvp.support.cn_trading_days <取数日>`，与资讯 MCP 时间窗、`meta.json` 对齐（见 **`MCP_资讯_取数.md`** 第 4.0 节）。

### 6.2 常用变量与参数

| 变量 / 参数 | 含义 |
|-------------|------|
| `GOT_SNAPSHOT_DATE` / `--snapshot-date` | 与 **`data/snapshot_{D}/`** 目录名、`{父目录}/{D}/` 对齐；未设则默认本机当天。 |
| `GOT_AGENT_OUTPUT_DIR` / `--agent-dir` | Agent JSON 的**父目录**；实际读取 **`父目录/{D}/`**。 |
| `GOT_DECISION_ONLY` / `--decision-only` | 仅决策链读盘模式（见**第 5 节**）。 |

可复制根目录 **`.env.example`** 为 **`.env`**（`.gitignore` 已忽略 `.env`）。

### 6.3 推荐执行顺序（新手上手）

1. 按 **`MCP_宏观_EDB_取数.md`**、**`MCP_资讯_取数.md`** 用 MCP 写入 **`src/got_mvp/data/snapshot_{D}/`**（`meta.json` 中 **`snapshot_date` = D**）。
2. 按 **`prompt_md/节点/*.md`** 生成 8 个节点 JSON，放入 **`{父目录}/{D}/`**。
3. 运行（**`D`** 与快照一致；仓库自带示例日 **`2026-05-03`** 可对齐试跑）：

```powershell
$env:GOT_AGENT_OUTPUT_DIR="你的父目录"
$env:GOT_SNAPSHOT_DATE="2026-05-03"
python -m src.got_mvp.run_mvp
```

或一行：`python -m src.got_mvp.run_mvp --agent-dir 父目录 --snapshot-date D`

缺快照或与 `meta.snapshot_date` 不一致时会报错；仅当目录与日期未就绪时才会缺文件。

---

## 7. 一次 `run_mvp` 的终端产出

stdout 为一份 JSON，主要键包括：

- **`final_output`**：对外结论（读盘模式下通常即 **`DecisionNode`** 内容）。
- **`aggregate`**、**`critic`**、**`human_input_for_decision`**（可能为 `null`）。
- **`evaluation`**：矛盾粗检摘要（含 **`evaluation_output_path`**）。
- **`observability`**：`agent_outputs_dir`、`evaluation_output_path`、`decision_only`、耗时、prompt 路径、**`logs`**。

**说明**：当前 **`evaluation`** 仅汇总五路输入的 **`evidence`** 与「归并 + 决策」合并文本做程序化粗检；**未**把 **`HumanInput_{D}.json`** 正文纳入该粗检（人类约束仍以决策/批判叙述为准）。

---

## 8. Python 执行链（主控）

| 顺序 | 模块 | 作用 |
|------|------|------|
| 1 | `run_mvp.py` | 解析 CLI / 环境变量，调用 `graph.run_graph` 与 `evaluation.evaluate_run`，打印 JSON。 |
| 2 | `graph.py` | `build_initial_state`：读快照、解析 Agent 路径、**`ensure_human_input_stub`**；`run_graph(..., decision_only=…)`：LangGraph **`invoke`** 或 **`run_graph_sequential`**，或 **`_run_decision_only_pipeline`**。 |
| 3 | `support/snapshot_loader.py` | 读 **`data/snapshot_{D}/`** → `snapshot_inputs`；**`resolved_snapshot_date`**。 |
| 4 | `nodes.py` | 读各 `*.json` 并 **`_validate_agent_report`**；决策阶段读 **`HumanInput_{D}.json`**。 |
| 5 | `support/node_output_json.py` | 节点 JSON 路径；**`HumanInput_{D}`** 占位与可选读入。 |
| 6 | `evaluation.py` | 写 **`data/evaluation/{D}/contradiction_evaluation.json`**，返回摘要。 |
| 7 | `state_types.py` | **`GoTState`** / **`RunMeta`** 类型。 |

---

## 9. 取数说明（链外、MCP 侧）

取数**不**被 `import` 进 `run_mvp`，但决定快照是否齐全。详细字段、query 与时间窗见：

- [`src/got_mvp/prompt_md/取数/MCP_宏观_EDB_取数.md`](./src/got_mvp/prompt_md/取数/MCP_宏观_EDB_取数.md)
- [`src/got_mvp/prompt_md/取数/MCP_资讯_取数.md`](./src/got_mvp/prompt_md/取数/MCP_资讯_取数.md)

**与五路节点的关系**：`CNMacroData` 节点材料来自 **`CNMacroData.json`**（不含上证字段）；**`SSEIndex.json`** 供归并/决策与指数锚对照。

---

## 10. 独立脚本（不参与 `run_mvp`）

| 命令 | 作用 |
|------|------|
| `python -m src.got_mvp.support.cn_trading_days YYYY-MM-DD` | 推算上一交易日与 `search_news` 的 `time_start` / `time_end`。 |
| `python -m src.got_mvp.support.build_snapshot_news_dedupe_*`（文件名须含 `dedupe`） | 手工合并去重资讯快照；按需运行。 |

---

## 11. Agent 读盘与回流

从目录读取时**不会**自动多轮批判回流；若要改结论，请改对应 JSON 后重新执行 **`run_mvp`**（或 **`--decision-only`**，见**第 5 节**）。
