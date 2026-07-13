<div align="center">

<img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/MCP-Anthropic-FF6B35?style=for-the-badge" />
<img src="https://img.shields.io/badge/A2A-Google-4285F4?style=for-the-badge&logo=google&logoColor=white" />
<img src="https://img.shields.io/badge/LangGraph-0.1.5-FF6B6B?style=for-the-badge" />
<img src="https://img.shields.io/badge/Groq-LLaMA3-F55036?style=for-the-badge" />
<img src="https://img.shields.io/badge/Neo4j-5.20-008CC1?style=for-the-badge&logo=neo4j&logoColor=white" />
<img src="https://img.shields.io/badge/SQLite-Audit_Log-003B57?style=for-the-badge&logo=sqlite&logoColor=white" />

# 🤖 Nexus AI

### Autonomous Developer Intelligence Network

> Give it one plain English instruction.
> It plans, writes code, reviews, tests, commits and ships a GitHub PR.
> Fully autonomous. Safety by design.

[Architecture](#architecture) • [Why MCP + A2A](#engineering-decisions) • [Agents](#agents) • [Safety](#safety-system) • [CLI](#cli) • [Setup](#setup)

</div>

---

## 📌 Overview

Nexus AI is an autonomous developer assistant that replaces manual development tasks with a coordinated network of specialized AI agents. Unlike traditional AI coding tools where humans trigger every action, Nexus AI operates end-to-end from a single instruction:

```
$ nexus run "add rate limiting to the review endpoint"

📋 Plan created: 8 steps
🌿 Branch created from main
💻 CoderAgent wrote the implementation
🔍 ReviewerAgent approved (score: 92/100)
🔒 SecurityAgent cleared (0 findings)
🧪 TesterAgent wrote and ran tests
✔️ ValidatorAgent approved (confidence: 97%)
🔗 PR #47 created: github.com/owner/repo/pull/47

Total time: 52 seconds
```

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🧠 6-Agent Peer Network | Specialized agents communicate via A2A protocol |
| 🔧 18 MCP Tools | File, git, test, and search tools for real codebase access |
| 🛡️ Risk-Based Safety | Three-tier classification — AUTO / CONFIRM / BLOCKED |
| ↩️ Automatic Rollback | File backup before every write, one-command restore |
| 📝 Audit Log | Full SQLite operation history with agent actions |
| 🔄 LLM Fallback | Auto-switches models on rate limits |
| 🌐 Neo4j Integration | Dependency-aware code changes |
| 💻 CLI Interface | 7 commands for full terminal control |

---

## 🏗️ High-Level Design (HLD)

### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                       │
│              CLI (nexus run "instruction")              │
│         7 commands: run, plan, ask, status,             │
│              agents, history, rollback                  │
└─────────────────────────────┬───────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────┐
│                 ORCHESTRATION LAYER                     │
│              NexusOrchestrator                          │
│                                                         │
│   Step 1 → PlannerAgent (task decomposition)           │
│   Step 2 → Branch creation (git)                       │
│   Step 3 → CoderAgent (implementation)                 │
│   Step 4 → ReviewerAgent + SecurityAgent (parallel)    │
│   Step 5 → TesterAgent (tests)                         │
│   Step 6 → ValidatorAgent (confidence scoring)         │
│   Step 7 → Commit + Push + PR creation                 │
└─────────────────────────────┬───────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────┐
│                   A2A PROTOCOL LAYER                    │
│              Agent-to-Agent Communication               │
│                                                         │
│  ┌──────────┐  REQUEST   ┌──────────────┐              │
│  │ Planner  │──────────► │    Coder     │              │
│  └──────────┘            └──────┬───────┘              │
│                                 │ DELEGATE              │
│                    ┌────────────▼────────────┐          │
│                    │  Reviewer  │  Security  │          │
│                    │  (peers — talk directly)│          │
│                    └────────────┬────────────┘          │
│                                 │ APPROVE/REJECT        │
│                    ┌────────────▼────────────┐          │
│                    │  Tester    │  Validator │          │
│                    └────────────────────────┘           │
└─────────────────────────────┬───────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────┐
│                    MCP TOOL LAYER                       │
│         18 Tools — Real Codebase Access                 │
│                                                         │
│  File Tools    → read, write, list, search, explain    │
│  Git Tools     → branch, commit, push, PR, history     │
│  Test Tools    → run, write, coverage, list            │
│  Search Tools  → pattern, semantic, function, imports  │
└──────────┬──────────────┬──────────────┬───────────────┘
           │              │              │
    ┌──────▼─────┐ ┌──────▼─────┐ ┌────▼──────────┐
    │ File System│ │   GitHub   │ │  Groq LLM API │
    │ (codebase) │ │    API     │ │ + Neo4j Graph │
    └────────────┘ └────────────┘ └───────────────┘
```

---

### Data Flow — End to End

```
User runs: nexus run "add error handling to main.py"
                         │
                         ▼
              NexusOrchestrator.run()
                         │
          ┌──────────────▼──────────────┐
          │       PlannerAgent          │
          │  LLM → 8-step plan JSON     │
          │  Risk assessment per step   │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │      Git: create_branch     │
          │  checkout main → new branch │
          │  nexus/{id}/instruction     │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │         CoderAgent          │
          │  semantic_search → files    │
          │  read_file → context        │
          │  LLM → solution JSON        │
          │  write_file → backup first  │
          │  commit_changes → git       │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │  ReviewerAgent  SecurityAgent│
          │  (run in parallel via A2A)  │
          │  read_file → review code    │
          │  LLM → quality score 0-100  │
          │  pattern scan → vulns       │
          │  LLM → security findings    │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │         TesterAgent         │
          │  run_tests → existing suite │
          │  LLM → generate test file   │
          │  write_file → tests/*.py    │
          │  run_tests → verify passing │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │        ValidatorAgent       │
          │  Confidence scoring:        │
          │  code(20) + review(25)      │
          │  + security(30) + test(25)  │
          │  LLM → executive summary    │
          │  Go/No-Go decision          │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │      Git: create_pr         │
          │  push branch → GitHub       │
          │  check existing PRs         │
          │  POST /pulls API            │
          │  Return PR URL              │
          └─────────────────────────────┘
```

---

### A2A Message Schema

```python
@dataclass
class A2AMessage:
    from_agent:   str           # sender agent ID
    to_agent:     str           # receiver agent ID
    message_type: MessageType   # REQUEST/RESPONSE/DELEGATE
    content:      dict          # payload
    priority:     Priority      # LOW/MEDIUM/HIGH/URGENT
    message_id:   str           # unique ID
    timestamp:    str           # ISO format
    reply_to:     str | None    # threading
    task_id:      str | None    # task grouping

# Message Types
REQUEST   → Ask agent to do something
RESPONSE  → Reply to request
BROADCAST → Send to all agents
DELEGATE  → Hand off a subtask
APPROVE   → Approve proposed action
REJECT    → Reject proposed action
STATUS    → Progress update
COMPLETE  → Task finished
```

---

### Safety System Schema

```
Operation Classification:

LOW RISK (AUTO — no confirmation)
├── read_file
├── list_files
├── search_codebase
├── query_dependencies
├── run_tests
├── analyze_code
└── semantic_search

MEDIUM RISK (AUTO in balanced, CONFIRM in strict)
├── write_file          ← backs up first
├── create_file
├── create_branch
├── create_pr
├── install_dependency
└── refactor_code

HIGH RISK (BLOCKED — never executes)
├── delete_file
├── merge_pr
├── deploy_production
├── modify_env
├── drop_database
├── modify_secrets
└── push_to_main

Safety Levels:
strict   → LOW auto, MEDIUM confirm, HIGH blocked
balanced → LOW + MEDIUM auto, HIGH blocked
auto     → LOW + MEDIUM auto, HIGH blocked
```

---


## 🎯 Engineering Decisions

---

### Why MCP (Model Context Protocol)?

**Problem:** Traditional LLM applications need humans to paste code, manually trigger actions, and copy results. There's no way for AI to directly access real systems.

**Decision:** Use Anthropic's MCP protocol (2024) to expose real tools to AI agents.

```
Without MCP:
Human copies code → pastes to LLM → copies result → pastes back
Every step manual, error prone, slow

With MCP:
Agent calls read_file("main.py") → gets actual content
Agent calls write_file("main.py", new_content) → actually writes
Agent calls run_tests() → gets real test results
Agent calls create_pr(...) → real PR created on GitHub

Zero human copy-paste. Zero manual file management.
```

---

### Why A2A (Agent to Agent Protocol)?

**Problem:** Traditional multi-agent systems use a central orchestrator that controls all agents. This creates a single point of failure and limits agent autonomy.

```
Traditional:
Orchestrator → Agent A (waits)
Orchestrator → Agent B (waits)
Orchestrator → Agent C (waits)
Orchestrator merges results

Problems:
- Orchestrator must know everything
- Agents cannot talk to each other
- Adding new agent requires orchestrator change
- One orchestrator failure = total failure
```

**Decision:** Use Google's A2A protocol (2025) for peer agent communication.

```
A2A (what Nexus AI uses):
ReviewerAgent → "line 42 has a bug" → CoderAgent
CoderAgent    → "fixed, re-review"  → ReviewerAgent
SecurityAgent → "found injection"   → interrupts everyone
TesterAgent   → "tests written"     → notifies Validator

Benefits:
- Agents are peers — no single boss
- Direct communication = faster
- New agents plug in via capability registry
- One agent failure doesn't kill pipeline
```

---

## 🛡️ Safety System

### Three-Tier Risk Classification

```
Every MCP tool call goes through:

check_operation(operation, safety_level)
         │
         ├── HIGH RISK? → BLOCK immediately
         │   Never executes regardless of instruction
         │
         ├── LOW RISK? → AUTO execute
         │   No confirmation needed
         │
         └── MEDIUM RISK?
             ├── safety=strict  → CONFIRM (show diff, ask yes/no)
             ├── safety=balanced → AUTO execute
             └── safety=auto    → AUTO execute
```

### Automatic Rollback System

```
Before every write_file():

1. Log operation to SQLite
   operations table: id, timestamp, operation, file_path

2. Backup original file
   .nexus_backups/20260712_103457_core_config.py

3. Write new content

4. Mark operation complete

On rollback:
nexus rollback

→ Find latest completed operation
→ Restore backup files
→ Mark as rolled_back in audit log
→ All in under 1 second
```

### What Is Always Blocked

```
No matter what instruction you give:

nexus run "delete all test files"
→ SecurityAgent blocks delete_file
→ Task fails safely
→ Nothing deleted

nexus run "merge the PR automatically"
→ merge_pr is permanently blocked
→ Humans always approve merges

nexus run "update the .env with new keys"
→ modify_env is permanently blocked
→ Secrets are always protected
```

---

## 🔄 Failure Handling

### LLM Rate Limit Handling

```
Groq returns 429 Too Many Requests
         │
         ▼
core/llm.py: _model_chain() builds fallback list
[llama-3.3-70b, llama-3.1-8b-instant]
         │
         ▼
Try llama-3.3-70b → 429
         │
         ▼
Log warning: "Rate limit on 70b, trying fallback"
         │
         ▼
Try llama-3.1-8b-instant → 200 OK
         │
         ▼
Log warning: "Succeeded with fallback model"
         │
         ▼
Return result transparently
No user-visible failure
```

---

## 📊 Metrics and Observability

### Confidence Score Breakdown

```
Every task produces a confidence score 0-100%:

┌─────────────────────────────────────────────┐
│ Metric          Weight   How Calculated     │
├─────────────────────────────────────────────┤
│ Code Written      20%   success bool        │
│ Review Quality    25%   25 × quality/100    │
│ Security Clear    30%   approved bool       │
│ Tests Passing     25%   passed/total ratio  │
├─────────────────────────────────────────────┤
│ Total            100%   sum of above        │
│ Threshold         70%   minimum to approve  │
└─────────────────────────────────────────────┘

Real example from run:
Code: 20 + Review(90/100): 22.5 + Security: 30 + Tests: 25
= 97.5% → APPROVED ✅
```

---

## 🤖 Agents

| Agent | Capabilities | Temperature | Key Tool |
|---|---|---|---|
| **PlannerAgent** | planning, task_decomposition | 0.2 | LLM reasoning |
| **CoderAgent** | code_writing, bug_fixing | 0.2 | write_file + LLM |
| **ReviewerAgent** | code_review, peer_review | 0.1 | read_file + LLM |
| **SecurityAgent** | security_scan, secret_detection | 0.1 | pattern scan + LLM |
| **TesterAgent** | test_execution, test_writing | 0.2 | run_tests + LLM |
| **ValidatorAgent** | validation, confidence_scoring | 0.3 | scoring formula |

---

## ⚙️ Setup

### Prerequisites

```
Python 3.11+
Git repository to operate on
Groq API key (free at console.groq.com)
GitHub Personal Access Token
Neo4j Aura instance (free tier)
```

### Installation

```bash
git clone https://github.com/kalyan4270/nexus-ai.git
cd nexus-ai

python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # Mac/Linux

pip install -r requirements.txt
pip install -e .
```

### Environment Variables

```env
# LLM
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_FALLBACK_MODELS=llama-3.1-8b-instant

# GitHub
GITHUB_TOKEN=your_github_token

# Neo4j
NEO4J_URI=neo4j+ssc://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# Nexus Config
TARGET_REPO_PATH=your-repo-path
SAFETY_LEVEL=balanced
AUTO_CREATE_PR=true
AUTO_RUN_TESTS=true
```

### Quick Start

```bash
# Check agents are ready
nexus status

# Ask about your codebase
nexus ask "what does main.py do?"

# Preview a task
nexus plan "add error handling to main.py"

# Run your first autonomous task
nexus run "add docstrings to core/config.py"
```

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Agent Protocol** | A2A (Google 2025) | Peer communication, no central boss |
| **Tool Protocol** | MCP (Anthropic 2024) | Standard tool interface, IDE compatible |
| **Orchestration** | LangGraph | State machine for agent workflow |
| **LLM Provider** | Groq LLaMA3 70B | Free tier, fast inference |
| **LLM Fallback** | Groq LLaMA3 8B | Auto-switch on rate limits |
| **Knowledge Graph** | Neo4j | Dependency relationship traversal |
| **Git Automation** | GitPython | Programmatic git operations |
| **CLI** | Click + Rich | Beautiful terminal interface |
| **Audit Storage** | SQLite | Zero-setup, built-in Python |
| **Config** | Frozen dataclass | Immutable, thread-safe, zero deps |

---

## 🔮 Future Enhancements

- [ ] Browser-based UI for visual agent workflow
- [ ] WebSocket for real-time agent progress streaming
- [ ] Support for JavaScript and Java codebases
- [ ] Multi-repo operations (change across services)
- [ ] Slack/Teams integration for PR notifications
- [ ] Docker containerization
- [ ] Agent memory across sessions
- [ ] Cost tracking per task

---

## 👤 Author

**Chodabattula Yaswanth**
- GitHub: [@kalyan4270](https://github.com/kalyan4270)
- LinkedIn: [Yaswanth](https://linkedin.com/in/chodabattula-yaswanth-venkata-kalyan-702b9523a)
- Portfolio: [yaswanth-portfolio](https://yaswanth-portfolio-v4uc.vercel.app/)

---

<div align="center">

Built with MCP • A2A • LangGraph • Groq • Neo4j • GitPython

*"Give it one instruction. It ships the code."*

</div>