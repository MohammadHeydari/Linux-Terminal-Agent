import subprocess
import requests
import json
import uuid
import time

# YOUR IP
OLLAMA_URL = "http://YOUR IP:11434/api/chat"
MODEL_NAME = "deepseek-coder:6.7b"

DATASET_FILE = "dataset.jsonl"
SAFE_ROOT = "/root/projects/"

# -----------------------------
# SAFETY CONFIG
# -----------------------------

ALLOWED_COMMANDS = ["ls", "find", "wc", "pwd", "du", "cat"]
BLOCKED_PATTERNS = ["find /", "rm -rf", "mkfs", "dd if=", ":(){:|:&};:"]

MAX_CMD_LEN = 80
MAX_OUTPUT_LINES = 30


# -----------------------------
# TASKS (SAFE)
# -----------------------------

def generate_tasks():
    return [
        "find all python files in current directory",
        "count lines in agent.py",
        "show current directory",
        "list files sorted by size in current directory",
        "print working directory"
    ]


# -----------------------------
# JSON PARSER (ROBUST)
# -----------------------------

def extract_json(text):
    try:
        text = text.replace("```json", "").replace("```bash", "").replace("```", "")
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except:
        return None


# -----------------------------
# SAFETY CHECK
# -----------------------------

def is_safe(cmd):
    if not cmd:
        return False

    if len(cmd) > MAX_CMD_LEN:
        return False

    if any(b in cmd for b in BLOCKED_PATTERNS):
        return False

    return any(cmd.startswith(a) for a in ALLOWED_COMMANDS)


# -----------------------------
# SAFE EXECUTION
# -----------------------------

def run_cmd(cmd):
    try:
        cmd = cmd.replace("find /", f"find {SAFE_ROOT}")

        result = subprocess.getoutput(f"timeout 3s {cmd}")

        # truncate output
        lines = result.split("\n")
        return "\n".join(lines[:MAX_OUTPUT_LINES])

    except Exception as e:
        return f"ERROR: {str(e)}"


# -----------------------------
# AGENT LOOP
# -----------------------------

def run_agent(task, max_steps=4):

    history = []
    trajectory = []

    last_cmd = None
    repeat_count = 0

    for step in range(max_steps):

        prompt = f"""
        You are a STRICT Linux terminal agent for dataset generation.

        CRITICAL RULES:
        - You MUST use SIMPLE commands only
        - Avoid pipes unless absolutely necessary
        - NEVER use complex pipelines like grep, awk, sort unless asked
        - NEVER repeat same command twice
        - NEVER scan large directories recursively (/ or ~)
        - ONLY work inside current directory

        ALLOWED COMMANDS:
        - ls
        - pwd
        - wc -l filename
        - find . -name "*.py"
        - du -sh *

        Task:
        {task}

        History (last 3 steps only):
        {json.dumps(history[-3:], indent=2)}

        Return ONLY valid JSON:
        {{
          "thought": "...",
          "cmd": "...",
          "done": false
        }}
"""

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                },
                timeout=40
            )

            text = response.json()["message"]["content"]
            print("\nMODEL:", text)

        except Exception as e:
            print("❌ API ERROR:", e)
            break

        data = extract_json(text)

        if not data:
            print("❌ JSON PARSE FAILED")
            break

        cmd = data.get("cmd")

        if not cmd:
            break

        # -----------------------------
        # LOOP DETECTION
        # -----------------------------

        if cmd == last_cmd:
            repeat_count += 1
        else:
            repeat_count = 0

        if repeat_count >= 2:
            print("🛑 LOOP DETECTED")
            return trajectory, False

        last_cmd = cmd

        # -----------------------------
        # SAFETY CHECK
        # -----------------------------

        if not is_safe(cmd):
            print("❌ UNSAFE COMMAND BLOCKED:", cmd)
            return trajectory, False

        print("EXEC:", cmd)

        output = run_cmd(cmd)
        print("OUTPUT:", output)

        trajectory.append({
            "thought": data.get("thought", ""),
            "cmd": cmd,
            "output": output
        })

        history.append({
            "cmd": cmd,
            "output": output
        })

        # -----------------------------
        # DONE CHECK
        # -----------------------------

        if data.get("done") is True:
            if "ERROR" in output or "No such file" in output:
                return trajectory, False

            if len(trajectory) == 0:
                return trajectory, False

            return trajectory, True

    return trajectory, False


# -----------------------------
# SAVE DATASET (ONLY GOOD DATA)
# -----------------------------

def save_sample(task, trajectory, success):

    if not success:
        return

    sample = {
        "id": str(uuid.uuid4()),
        "task": task,
        "trajectory": trajectory,
        "success": True,
        "timestamp": time.time()
    }

    with open(DATASET_FILE, "a") as f:
        f.write(json.dumps(sample) + "\n")


# -----------------------------
# MAIN
# -----------------------------

def main():
    tasks = generate_tasks()

    for task in tasks:
        print("\n" + "=" * 50)
        print("TASK:", task)

        trajectory, success = run_agent(task)

        save_sample(task, trajectory, success)

        print("SAVED | success:", success)


if __name__ == "__main__":
    main()