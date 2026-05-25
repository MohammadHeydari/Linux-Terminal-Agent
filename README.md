# Linux Terminal Agent (LLM-powered)

A collection of LLM-powered Linux terminal agents and dataset generation pipelines using Ollama.

This project explores how language models can safely generate and execute Linux commands, evaluate outcomes, and build datasets from execution trajectories.

---

## Features

- LLM-generated Linux commands (via Ollama)
- Safe command execution layer
- Iterative execution loop (agent reasoning cycles)
- JSON-based tool interface
- Trajectory logging for training data
- LLM + rule-based hybrid evaluation (judge system)
- Dataset generation pipeline with fallback and robustness features

---

## Models

Uses Ollama models (configurable):

- Default agent model: `deepseek-coder:6.7b`
- Alternative lightweight model: `gemma3:4b` (dataset pipeline)

---

## Project Structure

```bash
agent.py              # Simple prototype agent (basic loop)
agent_pro.py          # Agent + LLM judge + dataset logging
dataset_pipeline.py   # Production dataset generation pipeline
```

## How It Works
- User provides a task (e.g. "list files")
- LLM generates a Linux command in JSON format
- System validates and executes the command
- Output is stored in a trajectory
- Judge evaluates success (Optional) 
- Successful trajectories are saved as dataset samples

## RUN

Simple agent

```
python agent.py
```

Agent with judge + dataset logging

```
python agent_pro.py
```

Production dataset pipeline

```
python dataset_pipeline.py
```

## Output Format (Dataset)

```
{
  "id": "...",
  "task": "list files",
  "trajectory": [
    {
      "cmd": "ls",
      "output": "file1.py file2.py"
    }
  ],
  "success": true,
  "reason": "optional explanation"
}
```

## Notes
- Only safe Linux commands are allowed in agent.py
- Execution is time-limited
- Dangerous system commands are blocked
- Always review generated commands before production use

## Research Goal

This project explores:

- LLM-based tool use
- Self-improving agent loops
- Trajectory-based dataset creation
- Automatic evaluation of execution success

## Future Ideas
- ReAct-style reasoning agent
- Tool selection policy model
- Reinforcement learning from trajectories
- Web UI for agent monitoring
- Sandboxed execution environment

