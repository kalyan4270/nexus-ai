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

## 🔬 Low-Level Design (LLD)

### Agent Architecture

```
NexusAgent (Abstract Base Class)
├── Properties
│   ├── agent_id: str
│   ├── name: str
│   ├── capabilities: list[str]
│   └── current_task: str | None
│
├── A2A Methods
│   ├── handle_message(A2AMessage) → A2AMessage
│   ├── send_to(agent_id, task, context) → dict
│   └── delegate_to(capability, task) → dict
│
├── LLM Methods
│   └── think(prompt, max_tokens, temperature) → str
│
└── Task Methods
    ├── start_task(task_id)
    ├── complete_task()
    └── new_task_id() → str
         │
         ├── PlannerAgent     → planning, task_decomposition
         ├── CoderAgent       → code_writing, bug_fixing
         ├── ReviewerAgent    → code_review, peer_review
         ├── SecurityAgent    → security_scan, secret_detection
         ├── TesterAgent      → test_execution, test_writing
         └── ValidatorAgent   → validation, confidence_scoring
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

### Confidence Scoring Formula

```
ValidatorAgent calculates:

score = 0

Code written successfully  → +20 points
Reviewer approved          → +25 × (quality/100)
Security approved          → +30 points
  └── only false positives → +30 points
  └── low/medium issues    → +15 points
  └── critical found       → +0 points
Tests passing              → +25 points
  └── partial pass rate    → +25 × (passed/total)

Max score = 100
Minimum to approve = 70

Example:
Code: 20 + Review: 22.5 + Security: 30 + Tests: 25
= 97.5% confidence → APPROVED ✅
```

---

### Project Structure

```
nexus-ai/
├── cli.py                      # 7-command CLI interface
├── main.py                     # Entry point
├── setup.py                    # Installable package
├── mcp/
│   ├── server.py               # MCP server — 18 tools
│   └── tools/
│       ├── file_tools.py       # read/write/search files
│       ├── git_tools.py        # branch/commit/push/PR
│       ├── test_tools.py       # run/write/list tests
│       └── search_tools.py     # semantic/pattern search
├── a2a/
│   ├── protocol.py             # A2A message routing
│   └── registry.py             # Agent capability registry
├── agents/
│   ├── base.py                 # NexusAgent abstract class
│   ├── planner.py              # Task decomposition
│   ├── coder.py                # Code writing
│   ├── reviewer.py             # Code review peer
│   ├── security.py             # Security scanning
│   ├── tester.py               # Test execution + writing
│   ├── validator.py            # Confidence scoring
│   └── orchestrator.py        # End to end coordination
├── safety/
│   ├── classifier.py           # Risk classification
│   ├── guardrails.py           # Safety enforcement
│   └── rollback.py             # Backup + restore
├── core/
│   ├── config.py               # Frozen dataclass settings
│   ├── logging.py              # Structured logging
│   ├── exceptions.py           # Custom exception hierarchy
│   └── llm.py                  # Groq + fallback chain
├── graph/
│   ├── neo4j_client.py         # Graph queries
│   └── graph_builder.py        # Graph construction
└── storage/
    └── audit.py                # SQLite audit log
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

**Alternatives considered:**

| Option | Why Rejected |
|---|---|
| LangChain tools | Too opinionated, harder to expose via standard protocol |
| Custom REST API | Not interoperable with Claude Desktop or Cursor IDE |
| Direct function calls | Not discoverable, not standard, no ecosystem |
| MCP ✅ | Standard protocol, works with any MCP client, growing ecosystem |

---

### Why A2A (Agent to Agent Protocol)?

**Problem:** Traditional multi-agent systems use a central orchestrator that controls all agents. This creates a single point of failure and limits agent autonomy.

```
Traditional (what CodeGuardian uses):
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

**Alternatives considered:**

| Option | Why Rejected |
|---|---|
| LangGraph only | Good for workflows, not peer communication |
| CrewAI | Higher abstraction, less control over protocol |
| AutoGen | Microsoft specific, different protocol |
| Custom messaging | Not interoperable, reinventing the wheel |
| A2A ✅ | Google standard, growing ecosystem, proper peer model |

---

### Why Groq Over OpenAI?

**Problem:** OpenAI API costs money and has lower rate limits on free tier.

**Decision:** Use Groq with LLaMA3 as primary, with automatic fallback.

```python
# Fallback chain in core/llm.py
Primary:  llama-3.3-70b-versatile  (best quality)
Fallback: llama-3.1-8b-instant     (faster, higher limits)

On rate limit:
→ Automatically switches to fallback
→ Logs warning with model name
→ Returns result transparently
→ No user-visible failure
```

| Factor | OpenAI GPT-4 | Groq LLaMA3 |
|---|---|---|
| Cost | ~$30/1M tokens | Free tier |
| Speed | ~2-5 sec | ~0.5-1 sec |
| Rate limits | Paid tiers | 14,400 req/day free |
| Quality | Excellent | Very good |
| Decision | Too expensive for dev | ✅ Perfect for project |

---

### Why Neo4j Over PostgreSQL?

**Problem:** Understanding code dependencies requires traversing relationships across many hops — which files import which, which services call which APIs.

**Decision:** Neo4j graph database for dependency mapping.

```
PostgreSQL approach:
SELECT * FROM dependencies
JOIN files ON dependencies.target_id = files.id
WHERE dependencies.source_id = ?
-- needs recursive CTEs for multi-hop
-- expensive at scale

Neo4j approach:
MATCH (f:File {path: $path})
      <-[:IMPORTS|CALLS*1..5]-(dependent:File)
RETURN dependent.path
-- single query regardless of depth
-- relationship traversal is native
```

**When Neo4j wins:**
- Finding all downstream dependents of a changed file
- Detecting circular dependencies
- Mapping service-to-service call chains
- Historical PR impact analysis

---

### Why SQLite For Audit Log?

**Decision:** SQLite over Redis/PostgreSQL for audit storage.

```
Requirements:
→ Store operation history
→ Track file backups
→ Enable rollback queries
→ Zero infrastructure cost

SQLite wins because:
→ Zero setup — built into Python
→ File-based — works offline
→ Fast for read-heavy audit queries
→ No server to maintain
→ Perfect for single-machine dev tool
```

Production upgrade path: swap SQLite for PostgreSQL with zero code change — just update connection string.

---

### Why Frozen Dataclass For Config?

```python
@dataclass(frozen=True, slots=True)
class Settings:
    groq_api_key: str
    ...
```

**Decision:** Immutable frozen dataclass over Pydantic BaseSettings or plain dict.

```
Plain dict:
settings["key"] = "accidentally_changed"  # silent bug

Pydantic BaseSettings:
Good but heavy dependency for simple config

Frozen dataclass:
settings.groq_api_key = "new"  # raises FrozenInstanceError immediately
+ slots=True → memory efficient
+ @lru_cache → singleton, loaded once
+ Python stdlib → zero extra dependency
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

### Agent Failure Handling

```
If CoderAgent fails:
→ Returns {"success": False, "error": "..."}
→ Orchestrator catches → returns error result
→ Files NOT committed (nothing to rollback)
→ Branch still exists for debugging

If SecurityAgent finds critical issue:
→ Returns {"approved": False, "critical_count": 1}
→ Orchestrator blocks PR creation
→ Logs findings to terminal
→ Task marked failed with details

If PR creation fails 422:
→ Checks if P