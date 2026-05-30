"""结构化终端日志。"""
import sys
import time

# Windows GBK 终端无法输出 emoji，强制 UTF-8
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RESET = "\033[0m"
COLORS = {
    "ORC": "\033[95m",
    "SQL": "\033[94m",
    "RAG": "\033[92m",
    "RPT": "\033[93m",
    "SYS": "\033[96m",
    "ERR": "\033[91m",
}


def log_agent_step(agent: str, status: str, content: str = "", max_len: int = 500) -> None:
    color = COLORS.get(agent, "")
    timestamp = time.strftime("%H:%M:%S")
    text = str(content)
    clipped = text[:max_len] + ("..." if len(text) > max_len else "")

    print(f"\n{'-' * 50}")
    print(f"{color}[{agent}] {timestamp} {status}{RESET}")
    if clipped:
        print(clipped)