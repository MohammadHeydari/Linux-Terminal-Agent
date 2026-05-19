import subprocess
import requests
import json
import uuid
import time
import re

# your ip address
OLLAMA_URL = "http://YOUR-IP:11434/api/chat"
MODEL_NAME = "deepseek-coder:6.7b"

MAX_STEPS = 6
MAX_RETRIES = 3
MAX_OUTPUT = 1200
TIMEOUT = 3

SAFE_PREFIX = ("ls", "pwd", "find", "wc", "du", "grep", "cat", "echo", "head", "tail", "sort")


# ----------------------------
# JSON PARSER
# ----------------------------
def extract_json(text):
    try:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        return json.loads(m.group())
    except:
        return None


# ----------------------------
# SAFETY
# ----------------------------
def is_safe(cmd):
    cmd = cmd.strip()
    return cmd.startswith(SAFE_PREFIX)


# ----------------------------
# EXECUTOR
# ----------------------------
def run(cmd):
    try:
        p = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT
        )
        out = (p.stdout + p.stderr).strip()
        return out[:MAX_OUTPUT]
    except Exception as e:
        return f"ERROR: {str(e)}"


# ----------------------------
# VERIFIER (🔥 CORE OF LEVEL 3)
# ----------------------------
def verify(task, traj):
    if not traj:
        return "fail"

    last = traj[-1]["output"].lower()
    cmds = [t["cmd"] for t in traj]

    # ---- RULES ----

    if "current directory" in task:
        return "success" if "/" in last else "fail"

    if "list files" in task:
        return "success" if any("ls" in c for c in cmds) else "fail"

    if "python files" in task:
        return "success" if ".py" in last else "partial"

    if "count lines" in task:
        return "success" if "wc -l" in " ".join(cmds) else "fail"

    if "disk usage" in task:
        return "success" if "du" in " ".join(cmds) else "fail"

    if "first 5 lines" in task:
        return "success" if "head" in " ".join(cmds) else "fail"

    return "partial"


# ----------------------------
# REWARD FUNCTION
# ----------------------------
def reward(label, traj):
    base = {
        "success": 1.0,
        "partial": 0.5,
        "fail": 0.0
    }[label]

    penalty = 0.05 * len(traj)

    return max(base - penalty, 0)


# ----------------------------
# LLM CALL
# ----------------------------
def ask_llm(task, history, error=None):
    prompt = f"""
You are a Linux agent.

RULES:
- Return ONLY JSON
- One command only
- Must solve task minimally
- No explanation

TASK: {task}

ERROR: {error}

HISTORY:
{json.dumps(history[-4:], indent=2)}

FORMAT:
{{
  "thought": "short reasoning",
  "cmd": "bash command",
  "done": false
}}
"""

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            },
            timeout=20
        )
        return r.json()["message"]["content"]
    except:
        return None


# ----------------------------
# LOOP DETECT
# ----------------------------
def is_loop(history, cmd):
    return cmd in [h["cmd"] for h in history[-3:]]


# ----------------------------
# AGENT
# ----------------------------
def run_agent(task):
    history = []
    error = None

    for _ in range(MAX_STEPS):

        for _ in range(MAX_RETRIES):
            raw = ask_llm(task, history, error)
            data = extract_json(raw or "")

            if not data:
                error = "json_fail"
                continue

            cmd = data.get("cmd", "").strip()

            if not cmd:
                error = "empty_cmd"
                continue

            if not is_safe(cmd):
                error = "unsafe"
                continue

            if is_loop(history, cmd):
                error = "loop"
                continue

            break
        else:
            return history, "fail"

        output = run(cmd)

        history.append({
            "cmd": cmd,
            "output": output
        })

        if data.get("done"):
            break

        error = None

    label = verify(task, history)
    return history, label


# ----------------------------
# DATASET SAVE (RL-ready)
# ----------------------------
def save(task, traj, label):
    sample = {
        "id": str(uuid.uuid4()),
        "task": task,
        "trajectory": traj,
        "label": label,
        "reward": reward(label, traj)
    }

    with open("dataset_v3.jsonl", "a") as f:
        f.write(json.dumps(sample) + "\n")


# ----------------------------
# TASKS
# ----------------------------
def tasks():
    return [
        "show current directory",
        "list files in current directory",
        "find python files",
        "count lines in agent.py",
        "show disk usage",
        "print first 5 lines of agent.py"
    ]


# ----------------------------
# MAIN
# ----------------------------
def main():
    print("LEVEL 3 DATASET PIPELINE")

    for t in tasks():
        print("\n" + "=" * 40)
        print("TASK:", t)

        traj, label = run_agent(t)

        print("LABEL:", label)

        save(t, traj, label)

        time.sleep(0.5)


if __name__ == "__main__":
    main()