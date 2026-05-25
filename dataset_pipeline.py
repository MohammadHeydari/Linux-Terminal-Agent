import subprocess
import requests
import json
import uuid
import time
import os

OLLAMA_URL = "http://10.29.201.75:11434/api/chat"
# MODEL = "deepseek-coder:6.7b"
MODEL = "gemma3:4b"

MAX_STEPS = 5
NUM_SAMPLES = 3

# CIRCUIT BREAKER
LLM_FAIL_COUNT = 0
LLM_DISABLED_UNTIL = 0


def llm_available():
    global LLM_DISABLED_UNTIL
    return time.time() > LLM_DISABLED_UNTIL


def mark_llm_failure():
    global LLM_FAIL_COUNT, LLM_DISABLED_UNTIL

    LLM_FAIL_COUNT += 1

    if LLM_FAIL_COUNT >= 3:
        print("[CIRCUIT BREAKER] LLM disabled for 60s")
        LLM_DISABLED_UNTIL = time.time() + 60
        LLM_FAIL_COUNT = 0


# SAFE REQUEST (ANTI-TIMEOUT)
def safe_request(payload, retries=5, base_timeout=20):
    for attempt in range(retries):
        try:
            timeout = base_timeout + (attempt * 10)

            r = requests.post(
                OLLAMA_URL,
                json=payload,
                timeout=timeout
            )

            if r.status_code != 200:
                raise Exception(f"Bad status {r.status_code}")

            data = r.json()

            if "message" not in data:
                raise Exception("Invalid response")

            return data["message"]["content"]

        except Exception as e:
            print(f"[LLM ERROR] attempt {attempt+1}: {e}")
            time.sleep(2 ** attempt)

    print("[FATAL] LLM unreachable")
    return None


# SHELL EXECUTION
def run_cmd(cmd):
    try:
        p = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        return (p.stdout + p.stderr).strip()
    except Exception as e:
        return f"ERROR: {str(e)}"


# FALLBACK (NO LLM)
def fallback_command(task):
    mapping = {
        "show current directory": "pwd",
        "list files": "ls",
        "find python files": "find . -name '*.py'",
        "count lines in agent_pro.py": "wc -l agent_pro.py",
        "print first 5 lines of agent_pro.py": "head -n 5 agent_pro.py"
    }
    return mapping.get(task)


# AGENT
def ask_agent(task, history):
    if not llm_available():
        return None

    prompt = f"""
You are a Linux terminal agent.

Rules:
- Return ONLY JSON
- NEVER use fake paths
- Use current directory (.)

History:
{history}

Task:
{task}

Format:
{{"cmd": "...", "done": false}}
"""

    text = safe_request({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    })

    if not text:
        mark_llm_failure()
        return None

    try:
        data = json.loads(text[text.find("{"):text.rfind("}")+1])
        return data
    except:
        mark_llm_failure()
        return None


# TRAJECTORY
def run_trajectory(task):
    trajectory = []
    history = ""

    for _ in range(MAX_STEPS):
        data = ask_agent(task, history)

        if not data:
            cmd = fallback_command(task)

            if not cmd:
                break

            output = run_cmd(cmd)

            trajectory.append({
                "cmd": cmd,
                "output": output,
                "fallback": True
            })

            history += f"\nCMD: {cmd}\nOUTPUT: {output}\n"
            continue

        cmd = data.get("cmd")
        if not cmd:
            break

        output = run_cmd(cmd)

        step = {
            "cmd": cmd,
            "output": output,
            "fallback": False
        }

        trajectory.append(step)

        history += f"\nCMD: {cmd}\nOUTPUT: {output}\n"

        if data.get("done"):
            break

    return trajectory


# RULE-BASED JUDGE
def ground_truth(task):
    if task == "show current directory":
        return os.getcwd()
    if task == "list files":
        return os.listdir(".")
    return None


def judge_execution(task, trajectory):
    if not trajectory:
        return None

    last = trajectory[-1]["output"]
    gt = ground_truth(task)

    if gt is None:
        return None

    if task == "show current directory":
        return last.strip() == gt

    if task == "list files":
        return all(f in last for f in gt)

    return None


# LLM JUDGE
def llm_judge(task, trajectory):
    if not llm_available():
        return False

    text = safe_request({
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": f"""
Return ONLY JSON:
{{"success": true/false}}

TASK: {task}
TRAJECTORY: {trajectory}
"""
        }],
        "stream": False
    })

    if not text:
        mark_llm_failure()
        return False

    try:
        return json.loads(text[text.find("{"):text.rfind("}")+1])["success"]
    except:
        mark_llm_failure()
        return False


# HYBRID JUDGE
def judge(task, trajectory):
    rule = judge_execution(task, trajectory)
    if rule is not None:
        return rule

    return llm_judge(task, trajectory)


# MULTI-SAMPLE
def collect_best(task):
    candidates = []

    for _ in range(NUM_SAMPLES):
        try:
            traj = run_trajectory(task)
            success = judge(task, traj)

            candidates.append({
                "trajectory": traj,
                "success": success
            })

        except Exception as e:
            print("[ROLLOUT ERROR]", e)

    if not candidates:
        return {"trajectory": [], "success": False}

    success_trajs = [c for c in candidates if c["success"]]

    if success_trajs:
        best = sorted(success_trajs, key=lambda x: len(x["trajectory"]))[0]
    else:
        best = sorted(candidates, key=lambda x: -len(x["trajectory"]))[0]

    return best


# SAVE
def save(sample):
    with open("dataset.jsonl", "a") as f:
        f.write(json.dumps(sample) + "\n")


# MAIN LOOP
def main():
    tasks = [
        "show current directory",
        "list files",
        "find python files",
        "count lines in agent_pro.py",
        "print first 5 lines of agent_pro.py"
    ]

    print("LEVEL 7 PRODUCTION PIPELINE")

    for epoch in range(3):
        print(f"\n===== EPOCH {epoch} =====")

        for task in tasks:
            print("\nTASK:", task)

            try:
                result = collect_best(task)

                print("SUCCESS:", result["success"])

                if result["success"]:
                    save({
                        "id": str(uuid.uuid4()),
                        "task": task,
                        "trajectory": result["trajectory"],
                        "success": True
                    })

            except Exception as e:
                print("[TASK FAILED HARD]", e)

        time.sleep(2)


if __name__ == "__main__":
    main()