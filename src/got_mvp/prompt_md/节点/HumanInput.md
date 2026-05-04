# 人类输入文件：`HumanInput_{YYYY-MM-DD}.json`

工程总览见仓库根目录 **[`README.md`](../../../../README.md) 第 5 节**。

由主控在**首次进入带 Agent 输出目录的运行**时**自动创建占位文件**（与当日 **`GOT_SNAPSHOT_DATE` / `--snapshot-date`** 同名）；人类在文件生成后自行编辑即可。**若文件已存在，主控不会覆盖**，避免冲掉已写内容。

## 路径与命名

- 与当日各节点 JSON 同级：`{父目录}/{YYYY-MM-DD}/HumanInput_{YYYY-MM-DD}.json`  
  例：`…/2026-05-03/HumanInput_2026-05-03.json`

## 填写规则

- **`human_note`**（字符串）：人类对本次决策的补充说明、约束或偏好；**留空或未改写**则主控**忽略**人类输入（与无补充等价）。
- 兼容键 **`report`**：与 `human_note` 二选一，语义相同（以非空为准）。
- **`evidence`**（字符串数组，可选）：希望决策侧显式引用的短句。
- **`_instruction`** 等以下划线开头的键仅作说明，可删可留；不参与「是否已填写」判断。

## 全流程结束后再改决策

当五路与归并等 JSON 已定型、**仅**想调整人类说明或**仅**让 Agent **重写 `DecisionNode.json`** 时：

1. 编辑本目录下的 **`HumanInput_{D}.json`**（按需）并/或更新 **`DecisionNode.json`**；**不要**要求重跑五路与归并（除非你真的改了上游）。
2. 执行：  
   `python -m src.got_mvp.run_mvp --agent-dir 父目录 --snapshot-date D --decision-only`  
   或设置环境变量 **`GOT_DECISION_ONLY=1`**。  
   该模式**顺序读盘**五路 → 归并 → 决策（重新载入人类输入与决策 JSON）→ 批判，**不经过 LangGraph 的批判回流**；终端汇总与 **`data/evaluation/{D}/`** 仍会更新。

完整重跑（含 LangGraph 条件回流）仍使用**不带** `--decision-only` 的默认命令。
