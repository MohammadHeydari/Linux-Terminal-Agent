import subprocess
import requests
import json
import uuid
import time
import re

# YOUR-IP
OLLAMA_URL = "http://YOUR-IP:11434/api/chat"
MODEL_NAME = "deepseek-coder:6.7b"

MAX_OUTPUT_CHARS = 2000
MAX_CMD_RUNTIME = 5

ALLOWED_COMMANDS = [
    "ls", "pwd", "find", "wc", "du", "grep", "cat", "echo", "head", "tail", "sort"
]


def safe_parse(text):
    try:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        return json.loads(match.group())
    except:
        return None


def is_safe(cmd: str):
    return any(cmd.strip().startswith(c) for c in ALLOWED_COMMANDS)


def run_cmd(cmd: str):
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=MAX_CMD_RUNTIME
        )
        output = result.stdout + result.stderr
        return output[:MAX_OUTPUT_CHARS]
    except Exception as e:
        return str(e)


def ask_llm(task, history):
    prompt = f"""
You are a safe Linux terminal agent.

RULES:
- Return ONLY valid JSON
- Never explain
- Choose ONE bash command
- Prefer safe commands (ls, find, pwd, wc, du, grep)
- Avoid system-wide scans like find / or cat huge files
- If task is done, set done=true

TASK: {task}

HISTORY:
{json.dumps(history[-5:], indent=2)}

FORMAT:
{{
  "thought": "...",
  "cmd": "...",
  "done": false
}}
"""

    r = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        },
        timeout=30
    )

    return r.json()["message"]["content"]


def run_agent(task, max_steps=6):
    history = []
    seen_cmds = set()

    for step in range(max_steps):

        text = ask_llm(task, history)
        data = safe_parse(text)

        if not data:
            print("❌ JSON FAIL → retrying")
            continue

        cmd = data.get("cmd")

        if not cmd:
            continue

        if cmd in seen_cmds:
            print("🛑 LOOP DETECTED")
            break

        if not is_safe(cmd):
            print("⛔ BLOCKED COMMAND:", cmd)
            continue

        seen_cmds.add(cmd)

        print("\nMODEL:", data)
        print("EXEC:", cmd)

        output = run_cmd(cmd)
        print("OUTPUT:", output)

        history.append({
            "cmd": cmd,
            "output": output
        })

        if data.get("done"):
            break

    return history

if __name__ == "__main__":
    print("AGENT STARTED")

    task = "show current directory"
    result = run_agent(task)

    print("\nFINAL RESULT:")
    print(result)