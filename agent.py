import subprocess
import requests
import json
import re

OLLAMA_URL = "http://YOURWINDOWS-IP-ADDRESS:11434/api/chat"
MODEL = "deepseek-coder:6.7b"

task = "find all python files in current directory"

history = []
MAX_STEPS = 15


# JSON extractor (robust)
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


# LLM call
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


# Safety (optional but recommended)
ALLOWED_PREFIXES = ["ls", "find", "pwd", "cat", "grep"]


def is_safe(cmd):
    return any(cmd.startswith(x) for x in ALLOWED_PREFIXES)

# Main loop
step = 0

while step < MAX_STEPS:

    step += 1

    prompt = f"""
You are a Linux terminal agent.

TASK:
{task}

HISTORY:
{history}

RULES:
- Output ONLY JSON
- No markdown
- No explanation

FORMAT:
{{"cmd": "...", "done": false}}

If task is complete set done=true.
"""

    text = ask_llm(prompt)
    print("\nMODEL:", text)

    data = extract_json(text)

    if not data:
        print("Invalid output → retry")
        history.append("INVALID_OUTPUT")
        continue

    cmd = data.get("cmd")

    if not cmd:
        continue

    # safety check
    if not is_safe(cmd):
        print("blocked unsafe command:", cmd)
        history.append(f"BLOCKED: {cmd}")
        continue

    print("EXEC:", cmd)

    output = subprocess.getoutput(cmd)
    print("OUTPUT:", output)

    history.append({
        "cmd": cmd,
        "output": output
    })

    if data.get("done"):
        print("DONE")
        break


print("\nFinal history:")
print(history)