"""结构化终端日志。"""
import time

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