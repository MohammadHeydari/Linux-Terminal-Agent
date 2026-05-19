import subprocess
import requests
import json
import re

OLLAMA_URL = "http://10.29.201.75:11434/api/chat"
MODEL = "deepseek-coder:6.7b"

task = "find all python files in current directory"

history = []
MAX_STEPS = 10


def extract_json(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        return None

    try:
        return json.loads(text[start:end+1])
    except:
        return None


def ask_llm(prompt):
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
    )
    return r.json()["message"]["content"]


step = 0

while step < MAX_STEPS:
    step += 1

    prompt = f"""
    You are a REAL terminal agent.

    You CAN execute commands via the system.

    Your job is to COMPLETE the task.

    TASK:
    {task}

    HISTORY:
    {history}

    RULES:
    - You are NOT a chatbot
    - You DO execute commands
    - DO NOT explain anything
    - DO NOT repeat the same command
    - If output already answers the task → set done=true

    FORMAT (strict JSON):
    {{
      "thought": "...",
      "action": "bash",
      "input": "...",
      "done": false
    }}
"""

    text = ask_llm(prompt)
    print("\nMODEL:", text)

    data = extract_json(text)

    if not data:
        history.append("INVALID OUTPUT")
        continue

    thought = data.get("thought")
    action = data.get("action")
    cmd = data.get("input")

    print("THOUGHT:", thought)
    print("ACTION:", cmd)

    if action != "bash":
        history.append("INVALID TOOL")
        continue

    try:
        output = subprocess.getoutput(cmd)
    except Exception as e:
        output = str(e)

    print("OUTPUT:", output)

    history.append({
        "thought": thought,
        "cmd": cmd,
        "output": output
    })

    if data.get("done"):
        print("DONE")
        break