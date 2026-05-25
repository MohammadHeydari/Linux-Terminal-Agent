import subprocess
import requests
import json
import uuid
import time

OLLAMA_URL = "http://10.29.201.75:11434/api/chat"
MODEL = "deepseek-coder:6.7b"
JUDGE_MODEL = "deepseek-coder:6.7b"

MAX_STEPS = 5


# -------------------------
# AGENT EXECUTION
# -------------------------
def run_cmd(cmd):
    try:
        p = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=4
        )
        return (p.stdout + p.stderr).strip()
    except Exception as e:
        return f"ERROR: {str(e)}"


def ask_agent(task):
    prompt = f"""
You are a Linux terminal agent.

Return ONLY JSON:
{{
  "cmd": "...",
  "done": false
}}

Task: {task}
"""

    r = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        },
        timeout=30
    )

    text = r.json()["message"]["content"]

    try:
        return json.loads(text[text.find("{"):text.rfind("}")+1])
    except:
        return None


# -------------------------
# JUDGE (MOST IMPORTANT PART)
# -------------------------
def judge(task, trajectory):
    prompt = f"""
You are a strict evaluator.

TASK:
{task}

TRAJECTORY:
{json.dumps(trajectory, indent=2)}

QUESTION:
Did the trajectory successfully solve the task?

Return ONLY JSON:
{{
  "success": true/false,
  "reason": "..."
}}
"""

    r = requests.post(
        OLLAMA_URL,
        json={
            "model": JUDGE_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        },
        timeout=30
    )

    text = r.json()["message"]["content"]

    try:
        return json.loads(text[text.find("{"):text.rfind("}")+1])
    except:
        return {"success": False, "reason": "parse_error"}


# -------------------------
# PIPELINE
# -------------------------
def run_task(task):
    trajectory = []

    for _ in range(MAX_STEPS):
        data = ask_agent(task)
        if not data:
            break

        cmd = data.get("cmd")
        if not cmd:
            break

        output = run_cmd(cmd)

        trajectory.append({
            "cmd": cmd,
            "output": output
        })

        if data.get("done"):
            break

    return trajectory


def save(task, trajectory, judge_result):
    sample = {
        "id": str(uuid.uuid4()),
        "task": task,
        "trajectory": trajectory,
        "success": judge_result["success"],
        "reason": judge_result.get("reason")
    }

    with open("dataset_v6.jsonl", "a") as f:
        f.write(json.dumps(sample) + "\n")


# -------------------------
# MAIN
# -------------------------
def main():
    tasks = [
        "show current directory",
        "list files",
        "find python files",
        "count lines in agent.py",
        "show disk usage",
        "print first 5 lines of agent.py"
    ]

    print("LEVEL 6 JUDGE PIPELINE")

    for task in tasks:
        print("\n" + "="*40)
        print("TASK:", task)

        traj = run_task(task)

        result = judge(task, traj)

        print("JUDGE:", result)

        save(task, traj, result)


if __name__ == "__main__":
    main()