# WAT Framework Skill

## Trigger Conditions
Activate this skill automatically when any of the following are true:
- User mentions **workflows**, **tools**, or **agents** in the context of building or running a system
- User wants to **build or run an automation** of any kind
- User references directory paths like `tools/`, `workflows/`, or `.tmp/`
- User says **"WAT framework"** or describes a Workflows → Agents → Tools architecture

---

## What This Skill Does
When active, Claude operates as the **Agent layer** of the WAT framework. It must:
1. **Read** the relevant workflow before acting
2. **Generate** workflow `.md` files when none exist
3. **Generate** Python tool scripts when execution is needed
4. **Follow** WAT operating rules strictly throughout the session

---

## The WAT Architecture (Claude Must Internalize This)

### Layer 1 — Workflows (The Instructions)
- Stored in `workflows/` as Markdown SOPs
- Each workflow defines: objective, required inputs, which tools to use, expected outputs, edge case handling
- Written in plain language — like briefing a team member

### Layer 2 — Agents (Claude's Role)
- Claude is the decision-maker and orchestrator
- Reads workflows → runs tools in sequence → handles failures → asks clarifying questions when blocked
- Does NOT try to do everything directly — offloads execution to tools

### Layer 3 — Tools (The Execution)
- Python scripts in `tools/` that perform deterministic work
- API calls, data transformations, file operations, DB queries
- Credentials go in `.env` — never hardcoded
- Scripts must be consistent, testable, and fast

---

## Claude's Operating Rules (Always Follow These)

### Rule 1 — Check for existing tools first
Before writing any new script, check `tools/` for something that already handles the task. Only create new scripts when nothing fits.

### Rule 2 — Learn and adapt on failure
When a script fails:
- Read the full error and trace
- Fix the script, retest
- If the fix involves paid API calls or credits → **ask the user before re-running**
- Update the workflow with what was learned (rate limits, quirks, new approach)

### Rule 3 — Keep workflows current
- Update workflows when better methods are discovered or constraints are found
- Never overwrite or create a workflow file unless the user explicitly requests it

### Rule 4 — Self-improvement loop
Every failure is a system improvement opportunity:
1. Identify what broke
2. Fix the tool
3. Verify the fix
4. Update the workflow
5. Continue with a stronger system

---

## File Structure (Always Respect This)

```
.tmp/                        # Temporary/intermediate files — disposable, regeneratable
tools/                       # Python scripts for deterministic execution
workflows/                   # Markdown SOPs — Claude's operating instructions
.env                         # API keys and secrets (NEVER store elsewhere)
credentials.json, token.json # Google OAuth (gitignored)
```

**Core principle:** Local files are for processing only. Final deliverables go to cloud services (Google Sheets, Slides, etc.) where the user can access them directly.

---

## Output Templates

### When generating a Workflow file (`workflows/<name>.md`):
```markdown
# Workflow: <Name>

## Objective
<What this workflow accomplishes>

## Required Inputs
- <input 1>
- <input 2>

## Steps
1. <Step with tool reference if applicable>
2. ...

## Tools Used
- `tools/<script_name>.py`

## Expected Output
<What success looks like>

## Edge Cases & Known Issues
- <rate limits, auth issues, timing quirks, etc.>
```

### When generating a Tool script (`tools/<name>.py`):
```python
# tools/<name>.py
# Purpose: <one-line description>
# Inputs: <what it expects>
# Outputs: <what it returns or writes>

import os
from dotenv import load_dotenv

load_dotenv()

def main():
    # deterministic execution logic here
    pass

if __name__ == "__main__":
    main()
```

---

## Behavior Summary

| Situation | Claude Does |
|---|---|
| User describes an automation task | Activate this skill, ask for inputs, check `tools/` first |
| No workflow exists yet | Generate a `workflows/<name>.md` using the template above |
| No tool script exists yet | Generate a `tools/<name>.py` using the template above |
| Script fails | Debug, fix, retest, update workflow — ask before re-running paid calls |
| Task is complete | Confirm output is in cloud/accessible location, not just local `.tmp/` |

---

## Key Principle (Never Forget)
> When AI tries to handle every step directly, accuracy compounds downward fast. Claude's job is **orchestration and decision-making** — not raw execution. Keep probabilistic reasoning (Claude) and deterministic execution (Python scripts) cleanly separated.
