"""相容入口:原本的 Claude 評測腳本已整合為 `python -m plc_st eval`(見 plc_st/llm_eval.py)。

    python run_claude_eval.py                                   # 等同 eval --provider claude(預設模型)
    python run_claude_eval.py --model claude-haiku-5-5 --model claude-sonnet-5-5 --repeat 3

2026-11-09 第一次評測的原始產出保留在 docs/claude_eval_artifacts/ 與 docs/claude_eval_results.json。
"""
import sys

from plc_st.cli import main

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--provider" not in args:
        args = ["--provider", "claude"] + args
    sys.exit(main(["eval"] + args))
