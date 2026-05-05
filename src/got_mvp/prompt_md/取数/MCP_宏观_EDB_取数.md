# MCP 宏观取数：EDB（中国 / 美国）

本文仅覆盖 **同花顺 iFinD EDB MCP**（`get_edb_data`）。**资讯检索**见 **[`MCP_资讯_取数.md`](./MCP_资讯_取数.md)**。宏观与资讯 JSON 写在同一目录 **`src/got_mvp/data/agent_input/snapshot_{YYYY-MM-DD}/`**，主控侧由 **`support.snapshot_loader`** 合并读取为 **`snapshot_inputs`**（**`SSEIndex`** 与 **`CNMacroData`** 分键），无需手工再拼一个大 JSON。

**项目锚定**：下游结论对标 **上证综指日度走势**；上证 **日度收益锚** 单独落在 **`SSEIndex.json`**，**不**写入 **`CNMacroData.json`**。`support.snapshot_loader` 读盘后 **`snapshot_inputs["SSEIndex"]`** 与 **`snapshot_inputs["CNMacroData"]`** 分键并存，供归并/决策等阶段作**基线对照**；**中国宏观节点（`CNMacroData`）的 Agent 输入仅使用 `CNMacroData.json`**，避免把指数序列当作同一轮宏观推理的输入。

---

## 〇、步骤 0：取数日与 MCP 区间（须先于 §三 调 `get_edb_data`）

统一由仓库内 **`python -m src.got_mvp.support.snapshot_fetch_context`** 推算（依赖 **`chinesecalendar`**，与资讯时间窗同源）：

```bash
# 在仓库根目录执行（与 `python -m src.got_mvp.run_mvp` 同源 path）
python -m src.got_mvp.support.snapshot_fetch_context
python -m src.got_mvp.support.snapshot_fetch_context 2026-05-03
python -m src.got_mvp.support.snapshot_fetch_context 2026-05-03 --write
```

- **省略日期**：使用本机 **`date.today()`**（系统日历日）作为**取数日**。  
- **`--write`**：写入 **`src/got_mvp/data/agent_input/snapshot_{YYYY-MM-DD}/fetch_context.json`**（与 `snapshot_loader` 路径一致）；目录不存在则创建。

从 **stdout JSON** 或 **`fetch_context.json`** 读取：

| 键 | 用途 |
|----|------|
| **`edb_sse_query_zh_template`** | **§3.1 上证综指** 近 **10 个交易日** 的完整自然语言 query（日度区间已按锚定交易日滚动，勿手填） |
| **`macro_monthly_compact_span`** / **`macro_monthly_query_segment_zh`** | **§3.2 月度** 表格中 `（YYYYMM-YYYYMM）每月数值` 占位，**以 JSON 为准** 替换文中示例 |
| **`meta_patch_suggested_fields`** | 建议合并进 **`meta.json`**（含 `snapshot_date`、`news_*`；与 **[`MCP_资讯_取数.md`](./MCP_资讯_取数.md) §4** 一致） |

**禁止**：在未跑上述步骤的情况下，凭估算填写上证 10 日 YYYYMMDD 区间或月度 YYYYMM 区间。

---

## 一、本模块写入哪些文件

相对项目根 **`src/got_mvp/data/agent_input/snapshot_{YYYY-MM-DD}/`**：

| 文件 | 说明 |
|------|------|
| **`meta.json`** | 与资讯共用；宏观刷新时填写 **`edb_query_window`**、**`refreshed_at`**（可与资讯后合并），**`snapshot_date`** 必须与目录名日期一致 |
| **`SSEIndex.json`** | **上证综指基线**：近 10 交易日收盘价序列等（键见 §2.0）；与 `CNMacroData.json` **物理分离**，由加载器合并进图状态时单独成块 **`SSEIndex`** |
| **`CNMacroData.json`** | 单个 JSON 对象，键与下节「中国宏观（不含上证序列）」一致（全部为字符串） |
| **`USMacroData.json`** | 单个 JSON 对象，键与下节「美国」字段一致 |

不在此写入 `MacroNews.json` / `MesoNews.json` / `MicroNews.json`。

---

## 二、字段契约（值由取数填充）

### 2.0 `SSEIndex.json` 内字段（上证基线，**勿**写入 `CNMacroData.json`）

**字符串建议**：数值、日期、摘要均为字符串。

| 字段 | 含义 |
|------|------|
| `sse_index_close_last10` | 上证综指收盘价，近 10 交易日「旧→新」逗号分隔 |
| `sse_index_dates_last10` | 与上对齐的 `YYYY-MM-DD`，共 10 个交易日 |
| `sse_index_daily_pct_last10` | 可选，同日涨跌幅%；无则 **`未取`** |
| `sse_index_trace_summary` | 概括近 10 日走势（震荡/趋势/波动等），**可多句、多段**，不限一句话 |

### 2.1 `CNMacroData.json` 内字段（中国宏观月度等；**不含** `sse_index_*`）

**字符串建议**：数值、日期、`summary` 均为字符串，便于下游直接序列化。

| 字段 | 含义 |
|------|------|
| `pmi` / `pmi_dates` | 制造业 PMI 近三期 |
| `cpi_yoy` / `cpi_yoy_dates` | CPI 同比近三期 |
| `credit_impulse` / `credit_impulse_dates` | 社融存量同比近三期 |
| `ppi_yoy` / `ppi_yoy_dates` | PPI 同比 |
| `cn_core_cpi_yoy` / `cn_core_cpi_yoy_dates` | 核心 CPI，无则 **未取** |
| `m2_yoy` / `m2_yoy_dates`、`m1_yoy` / `m1_yoy_dates` | M2、M1 |
| `social_financing_increment` / `_dates` | 社融增量 |
| `industrial_value_added_yoy` / `_dates` | 工业增加值当月同比 |
| `fixed_asset_investment_yoy` / `_dates` | 固定资产投资累计同比 |
| `retail_sales_yoy` / `_dates` | 社零当月同比 |
| `export_yoy` / `import_yoy` / `_dates` | 进出口同比 |
| `trade_balance_surplus` / `_dates` | 贸易顺差或差额 |
| `lpr_1y` / `mlf_rate` / `reverse_repo_7d` / `shibor_overnight` 及各自 `_dates` | 利率锚 |
| `urban_survey_unemployment` / `_dates`、`new_urban_employment_cumulative` / `_dates` | 就业 |
| `summary` | 中国侧综述：增长/物价/信用/外贸/利率/就业等；**可多句、多段**；**不必**复述上证逐日行情（指数见 **`SSEIndex.json`**） |

### 2.2 `USMacroData.json` 内字段

| 字段 | 含义 |
|------|------|
| `nonfarm` / `nonfarm_dates` | 非农变动近三期 |
| `core_cpi_yoy` / `core_cpi_yoy_dates` | 核心 CPI 同比 |
| `us_cpi_yoy` / `us_cpi_yoy_dates` | CPI 总同比 |
| `us_ism_manufacturing_pmi` / `_dates`、`us_markit_manufacturing_pmi` / `_dates` | 制造业 PMI |
| `fed_tone` | 联储口径短摘（也可 partly 来自资讯） |
| `summary` | 美国就业、通胀、景气外溢等综述；**可多句、多段** |

**对齐说明**：query 关键词与 **[《上证走势影响因素说明书》](../../../../上证走势影响因素说明书.md) §2.1** 一致，并含中国就业；详细 **query 模板**见下节表格。

---

## 三、EDB 调用与 query 模板

**服务标识**：`user-hexin-ifind-ds-edb-mcp`  
**工具**：`get_edb_data`，参数 `{"query": "<自然语言，含时间区间>"}`  

### 3.1 上证综指：近 10 个交易日（写入 **`SSEIndex.json`**，不写入 `CNMacroData.json`）

示例 query（**日期须来自 §〇 的 `edb_sse_query_zh_template`**，勿照抄下例）：

`上证综指收盘价 日度 （20260415-20260504）每日数值`

**截取**：返回行一般为 **[日期, 收盘价]**，**新→旧**；取 **前 10 行**为最近 10 个交易日。写入 **`SSEIndex.json`** 的 **`sse_index_*`** 时建议 **旧→新** 排列；涨跌幅无则填 **未取**。**`sse_index_trace_summary`** 必填。

### 3.2 月度序列（近三期）

时间窗口占位：`（202511-202604）每月数值`（示例；**实盘以 §〇 的 `macro_monthly_query_segment_zh` / `macro_monthly_compact_span` 为准**，按锚定交易日对应自然月滚动，略宽于三月以便取最近 3 个有效月）。

#### 3.2.1 中国

| 写入字段前缀 | query 示例 |
|--------------|------------|
| `pmi` | `中国制造业PMI 月度 （202511-202604）每月数值` |
| `cpi_yoy` | `中国CPI当月同比 月度 （202511-202604）每月数值` |
| `ppi_yoy` | `中国PPI当月同比 月度 （202511-202604）每月数值` |
| `cn_core_cpi_yoy` | `中国核心CPI 当月同比 月度 （202511-202604）每月数值` |
| `credit_impulse` | `中国社融规模存量同比 月度 （202511-202604）每月数值` |
| `m2_yoy` | `中国M2同比 月度 （202511-202604）每月数值` |
| `m1_yoy` | `中国M1同比 月度 （202511-202604）每月数值` |
| `social_financing_increment` | `社会融资规模增量 月度 （202511-202604）每月数值` |
| `industrial_value_added_yoy` | `中国工业增加值当月同比 月度 （202511-202604）每月数值` |
| `fixed_asset_investment_yoy` | `中国固定资产投资完成额累计同比 月度 （202511-202604）每月数值` |
| `retail_sales_yoy` | `中国社会消费品零售总额当月同比 月度 （202511-202604）每月数值` |
| `export_yoy` | `中国出口金额当月同比 月度 （202511-202604）每月数值` |
| `import_yoy` | `中国进口金额当月同比 月度 （202511-202604）每月数值` |
| `trade_balance_surplus` | `中国贸易差额 当月值 月度 …` 或 `贸易顺差 月度 …` |
| `lpr_1y` | `中国LPR1年期 月度 （202511-202604）每月数值` |
| `mlf_rate` | `MLF利率 月度 …` 或 `中期借贷便利 利率 月度 …` |
| `reverse_repo_7d` | `7天逆回购利率 月度 （202511-202604）每月数值` |
| `shibor_overnight` | `上海银行间同业拆放利率隔夜 月度 （202511-202604）每月数值` |
| `urban_survey_unemployment` | `中国城镇调查失业率 月度 （202511-202604）每月数值` |
| `new_urban_employment_cumulative` | `全国城镇新增就业人数累计值 月度 （202511-202604）每月数值` |

#### 3.2.2 美国

| 写入字段前缀 | query 示例 |
|--------------|------------|
| `nonfarm` | `美国新增非农就业人数当月值季调 月度 （202511-202604）每月数值` |
| `core_cpi_yoy` | `美国核心CPI不含食物能源当月同比 月度 （202511-202604）每月数值` |
| `us_cpi_yoy` | `美国CPI同比 月度 （202511-202604）每月数值` |
| `us_ism_manufacturing_pmi` | `美国ISM制造业PMI 月度 （202511-202604）每月数值` |
| `us_markit_manufacturing_pmi` | `美国Markit制造业PMI 月度 （202511-202604）每月数值` |

**近三期截取**（月度通用）：表格行为 **[日期, 数值]**，通常 **新→旧**；取 **前 3 行**；无序列填 **未取** 并在 `summary` 说明。

API **限频**时可分批 `sleep` 重试。

---

## 四、宏观自检

- [ ] `SSEIndex.json` / `CNMacroData.json` / `USMacroData.json` 可被 `json.load`，且为 **对象**
- [ ] **`CNMacroData.json` 内不含任何 `sse_index_*` 键**（上证字段仅在 **`SSEIndex.json`**）
- [ ] 上证综指 **10 个交易日** 与 **`SSEIndex.json`** 内 **`sse_index_trace_summary`** 一致
- [ ] 中国全表（含就业两项）、美国补充项已落字段，无数据标 **未取**
- [ ] **`meta.json`** 中 **`snapshot_date`** 与 **`data/agent_input/snapshot_{D}`** 目录名一致；EDB / 资讯相关区间与 **`fetch_context.json`**（或 **`snapshot_fetch_context` 最近一次输出）一致
