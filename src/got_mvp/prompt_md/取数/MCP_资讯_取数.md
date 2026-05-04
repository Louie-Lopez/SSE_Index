# MCP 资讯取数：宏观 / 中观 / 微观新闻

<!-- 工具约束：search_news 单次请求参数 size 有上限（当前同花顺 MCP 工具描述为 ≤20）；时间窗内「全量」资讯须靠多轮 query、合并去重逼近，见 §3.1。 -->

**落盘约定（与接口返回的区别）**：`search_news` 等接口返回里通常含 **`资讯标题`、`资讯内容`（片段）、`日期`、`URL`**。本项目的 **`MacroNews` / `MesoNews` / `MicroNews` 快照字段只写入「日期 + 标题」**（见 §二行格式），**不写入正文片段**；需要全文或更长片段时请用 **`URL`** 另行打开或二次请求。**`summary`** 为综述字段：**可多句、多段**，不限一句话；篇幅以说清要点为准（仍须为合法 JSON 字符串，换行可写 `\n`）。

本文仅覆盖 **同花顺 iFinD 资讯 MCP**（`search_news` / `search_trending_news` 等）。**宏观 EDB** 见 **[`MCP_宏观_EDB_取数.md`](./MCP_宏观_EDB_取数.md)**。与宏观共用目录 **`src/got_mvp/data/snapshot_{YYYY-MM-DD}/`**，与 **`SSEIndex.json`**、`CNMacroData.json` 等同层落盘即可。

---

## 一、本模块写入哪些文件

相对项目根 **`src/got_mvp/data/snapshot_{YYYY-MM-DD}/`**：

| 文件 | 说明 |
|------|------|
| **`meta.json`** | 与宏观共用；资讯刷新时填写 **`news_window`**、可更新 **`refreshed_at`** / **`source`** |
| **`MacroNews.json`** | 单个对象：**宏观**政策与流动性等 |
| **`MesoNews.json`** | 单个对象：**中观**产业与地产链等 |
| **`MicroNews.json`** | 单个对象：**微观**业绩与事件风险 |

**每条资讯层级各自独立成文件**，便于单独刷新与 diff。

---

## 二、各 JSON 内字段（字符串，或「标题行」字符串数组）

**与「窗口内全量资讯」的关系**：每个字段要么是一条 **UTF-8 字符串**（多标题用 `\n` 换行拼接），要么是 **`string[]` 数组**，**数组每一项对应 MCP 返回的一条资讯**（与逐行拼接等价，便于 diff 与机器校验）。元素格式均为：

`YYYY-MM-DD | 资讯标题`

**加载**：**`support.snapshot_loader`**（`read_snapshot_inputs` / `load_snapshot_inputs`）会将上述 **数组自动拼成换行字符串** 再写入图状态 **`snapshot_inputs`** 交给下游，故 **`summary`** 仍为单字符串；政策/流动性/产业等 **全量标题** 不得仅用综述代替。

（**不写** `资讯内容` 片段；字段内换行用 `\n`。若需附带 **`URL`** 便于溯源，可用 `YYYY-MM-DD | 资讯标题 | URL` 三列格式，但须在 `meta.json` 或本文件备注中固定列含义，且仍以标题为主、避免把长正文塞进第三列。）

### `MacroNews.json`

| 字段 | 含义 |
|------|------|
| `policy` | **时间窗内**与宏观政策相关的**全部**命中条目的 **日期+标题**（按上格式逐行拼接；无则写说明句） |
| `global_liquidity` | **时间窗内**与美元 / 流动性 / 汇率 / 外资等相关的**全部**条目的 **日期+标题** |
| `summary` | 对以上两类标题集合的**综述**（**不替代**逐行标题罗列） |

### `MesoNews.json`

| 字段 | 含义 |
|------|------|
| `tech` | **时间窗内**产业 / 科技链等检索的**全部**条目的 **日期+标题**（同上格式） |
| `property` | **时间窗内**地产或相关链条的**全部**条目的 **日期+标题** |
| `summary` | 中观综述；不替代标题全量罗列） |

### `MicroNews.json`

| 字段 | 含义 |
|------|------|
| `earnings` | **时间窗内**业绩 / 预告类**全部**条目的 **日期+标题** |
| `event_risk` | **时间窗内**事件与情绪风险类**全部**条目的 **日期+标题** |
| `summary` | 微观综述 ；不替代标题全量罗列） |

**与 `USMacroData` 的衔接**：联储口径可写在 **`USMacroData.json`** 的 **`fed_tone`**（属宏观 EDB 文件）；若仅跑资讯，也可在拉完新闻后手工合并进该文件，或下次跑 EDB 时补写。

---

## 三、服务与工具

**服务标识**：`user-hexin-ifind-ds-news-mcp`

| 工具 | 用途 | 典型参数 |
|------|------|----------|
| `search_news` | 关键词 + 时间范围 | `query`, `time_start`, `time_end`, `size`（≤20） |
| `search_trending_news` | 热点 | `keyword`, `time_scope`, `industry_name`, `size` 等 |

### 3.1 如何在「单次 ≤20 条」下逼近「窗口内全量」

目标：**在固定的 `time_start`～`time_end` 内，把该窗内能搜到的相关资讯尽量全部落库**，而不是只保留一两条摘要。

1. **单次拉满**：每条 `search_news` 调用将 **`size` 设为 20**（或工具允许的上限）。  
2. **多 query 穷尽**：同一主题下轮换关键词、同义词、细分实体（如「央行」「国常会」「财政部」「专项债」拆成多次），**固定时间窗不变**，将各次返回结果 **合并后按 URL 或「标题+日期」去重**；从每条记录 **仅抽取 `日期` + `资讯标题` 写入快照**（忽略 `资讯内容` 片段）。  
3. **主题分桶写入**：宏观政策类统一并入 `MacroNews.policy`；流动性类并入 `global_liquidity`；中观 / 微观同理对应 `MesoNews` / `MicroNews` 字段，避免同一稿在多个字段重复（若重复，保留一条并可在行尾标注 `[dup]`）。  
4. **工具若支持分页 / offset**（以当时 MCP 文档为准）：应对同一 `query` **翻页直到返回为空或少于 `size`**。  
5. **与 EDB 无关**：资讯只受 **资讯 MCP** 索引与检索语法限制；若某窗内确无命中，在该字段写 **「时间窗内无命中」** 并注明 query 列表，勿伪造。  
6. **离线「嵌入 MCP 返回 → 合并去重 → 写快照」脚本**（非主流程）：置于 **`src/got_mvp/support/`**，文件名**必须**含 **`dedupe`**（或与「去重」明确同义的英文片段，如 `dedup_`），并带取数日，例如 **`build_snapshot_news_dedupe_20260503.py`**；禁止与在线拉数脚本同名混淆。

**建议检索主题**（关键词可替换；每个主题建议多轮 query 直至连续两轮无新增）：

| 目标字段 | 示例 query / 说明 |
|----------|-------------------|
| `MacroNews.policy` | `货币政策 稳增长 财政部` |
| `MacroNews.global_liquidity` | `美元 流动性 汇率 外资` |
| `fed_tone`（写入 US 宏观文件） | `美联储 FOMC 利率` |
| `MesoNews` | `行业景气 开工率 制造业投资`；地产链写入 `property` |
| `MicroNews` | `业绩预告 增持 回购 龙头` |

---

## 四、时间窗（增量资讯）

拉取 **自上一交易日全日市收盘起，至本次取数当前时点** 期间的资讯——**本窗内所有与检索主题相关的、工具能返回的资讯条目都应纳入**（见 §3.1 多轮合并；不因「太长」而只挑一两条代表）。

### 4.0 必须先算日期再调 MCP（禁止拍脑袋区间）

1. **取数日**：与目录 **`snapshot_{YYYY-MM-DD}`** 及 **`meta.snapshot_date`** 一致（可为周末或法定假日；不要求当天开市）。  
2. **上一交易日**：严格早于取数日 0 点的、最近一次 **上交所交易日**（含国务院调休的周末补班）。仓库内用 **`src.got_mvp.support.cn_trading_days`**（依赖 **`chinesecalendar`**，见项目根 **`requirements.txt`**）统一推算，避免与真实休市错位。  
3. **命令行**（将 `YYYY-MM-DD` 换成取数日）：

```bash
# 在仓库根目录，PYTHONPATH 指向 src（与跑主控一致）
set PYTHONPATH=src
python -m src.got_mvp.support.cn_trading_days 2026-05-03
```

输出 JSON 中的 **`search_news.time_start` / `time_end`** 即为本次应传入 MCP 的日期；**不得**自行用「往前多估几天」代替上一交易日。  
4. **写入 `meta.json`**：除 **`news_window`** 人读说明外，须同步写入结构化字段（与上一步输出一致）：**`news_previous_trading_day`**、**`news_time_start`**、**`news_time_end`**，便于 diff 与复跑对齐。  
5. **无 `chinesecalendar` 时**：`support.cn_trading_days` 退化为「仅跳过周六日」；节假日边界可能偏差，**生产取数须安装依赖**。

其余语义：

6. **收盘时刻**：A 股日盘多按 **北京时间 15:00** 作为日盘结束参考。  
7. **MCP 仅支持日期**：`time_start` = **`news_time_start`**（= 上一交易日），`time_end` = **`news_time_end`**（= 取数日）；闭区间 `[time_start, time_end]` 覆盖取数日内的周末稿（以资讯 `日期` 字段为准筛增量）。  
8. **支持 ISO 时间**：若工具支持 **`time_start` / `time_end` 含时分**，优先用 **`上一交易日T15:00:00+08:00`** 至 **`当前时刻`**，与增量口径一致。  

**写入**：每条命中按 §二格式 **只追加「日期 + 标题」** 到对应字段字符串；**`summary` 仅作综述，不得用极简略写代替全量标题行**（综述本身允许多句、多段）。无结果时写简短说明，勿留空键。

---

## 五、资讯自检

- [ ] `MacroNews.json` / `MesoNews.json` / `MicroNews.json` 均为合法 JSON 对象  
- [ ] 各主题字段是否已通过 **多 query + 去重** 尽量覆盖 **时间窗内** 全部命中（而非仅 Top-1～3）  
- [ ] 单条 `size` 是否用满；无分页能力时是否已用 **轮换关键词** 榨干增量  
- [ ] 时间窗为 **上一交易日收盘后 → 当前取数时点**（或 ISO 精确窗），且与 **`meta.news_window`** / **`news_time_*`** 一致  
- [ ] **`meta.json`** 中 **`snapshot_date`** 与目录名一致；**`news_previous_trading_day`** 与 **`python -m src.got_mvp.support.cn_trading_days`** 输出一致  
- [ ] 若字段体积极大：仍属预期（全量**标题**）；正文细节不在快照内，若节点需要可提示依赖 URL 或二次拉取  
- [ ] 是否确认未把 **`资讯内容`** 片段拼进 `policy` 等字段（与「仅标题」约定一致）  
