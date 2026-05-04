# 【本地推理】将「节点说明 Markdown + 上下文 JSON」经子进程 stdin 交给用户配置的 CLI（如 Claude Code ``claude -p -``），解析 stdout 中的 JSON 对象。
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any


def extract_first_json_object(text: str) -> dict[str, Any]:
    """从模型 stdout 中取出第一个顶层 JSON 对象（容忍前后废话或 ```json 围栏）。"""
    if not text or not str(text).strip():
        raise ValueError("模型 stdout 为空")
    s = str(text).strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s, re.IGNORECASE)
    if fence:
        s = fence.group(1).strip()
    dec = json.JSONDecoder()
    i = s.find("{")
    if i < 0:
        raise ValueError("stdout 中未找到 JSON 对象起始 '{'")
    obj, _end = dec.raw_decode(s[i:])
    if not isinstance(obj, dict):
        raise ValueError("解析结果不是 JSON 对象")
    return obj


@dataclass
class LocalInferRunner:
    """由环境变量 ``GOT_LOCAL_INFER`` 解析 argv；整段 user 消息走 stdin（UTF-8）。"""

    argv: list[str]
    timeout_sec: float
    cwd: str | None

    @classmethod
    def from_env(cls) -> LocalInferRunner:
        raw = os.getenv("GOT_LOCAL_INFER", "").strip()
        if not raw:
            raise ValueError(
                "未设置环境变量 GOT_LOCAL_INFER。\n"
                "示例（stdin 为整段提示词，常见 Claude Code）：\n"
                "  PowerShell: $env:GOT_LOCAL_INFER='claude -p -'\n"
                "  bash: export GOT_LOCAL_INFER='claude -p -'\n"
                "请按你本机「本地 Claude CLI / Cursor 包装脚本」实际参数调整；首 token 为可执行文件。"
            )
        posix = os.name != "nt"
        argv = shlex.split(raw, posix=posix)
        if not argv:
            raise ValueError("GOT_LOCAL_INFER 解析后 argv 为空")
        timeout_sec = float(os.getenv("GOT_LOCAL_INFER_TIMEOUT_SEC", "900").strip() or "900")
        cwd_raw = os.getenv("GOT_LOCAL_INFER_CWD", "").strip()
        return cls(argv=argv, timeout_sec=timeout_sec, cwd=cwd_raw or None)

    def run(self, user_message: str) -> str:
        try:
            p = subprocess.run(
                self.argv,
                input=user_message,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_sec,
                cwd=self.cwd,
                shell=False,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                f"无法启动子进程，可执行文件可能不在 PATH: {self.argv[0]!r}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"本地推理超时（{self.timeout_sec}s）: {' '.join(self.argv)!r}") from e
        if p.returncode != 0:
            err = (p.stderr or "").strip()
            out = (p.stdout or "").strip()
            raise RuntimeError(
                f"本地推理退出码 {p.returncode}，命令: {' '.join(self.argv)!r}\n"
                f"stderr（节选）:\n{err[:4000]}\nstdout（节选）:\n{out[:2000]}"
            )
        return p.stdout or ""


def redact_argv_for_meta(argv: list[str]) -> list[str]:
    """写入 _generator 时的 argv 摘要（避免绝对路径过长）。"""
    if len(argv) <= 6:
        return list(argv)
    return [argv[0], *argv[1:3], "…", argv[-1]]
