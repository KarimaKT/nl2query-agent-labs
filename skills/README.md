# Copilot Studio Fabric NL2Query — Skill Library

Skills for building, deploying, comparing, and evaluating NL2Query agents on Power BI / Fabric using Copilot Studio.

Built by the Microsoft CAT team. CGO reference agent (TableTalk with Fabric) by [Nico Sprotti](https://github.com/NicoPilot-dev/TableTalkWithFabric).

---

## Before you start

The **deploy skills** (`/tabletalk-fabric-deploy`, `/fabric-analyst-deploy`) are self-contained — they include all commands and content needed to deploy a working agent. Read the prerequisites section of each skill before running.

The **pattern skills** (`/cgo-nl2query-patterns`, `/ngo-nl2query-patterns`, `/copilot-studio-new-orchestrator`) are reference materials. You do not need to read them before deploying, but they explain the design decisions and are essential if you want to customize the agents or troubleshoot issues.

---

## Decision guide

```
What do you want to do?
│
├── Deploy a CGO (classic orchestration) NL2Query agent
│   └── /tabletalk-fabric-deploy
│
├── Deploy a New Generative Orchestrator NL2Query agent
│   └── /fabric-analyst-deploy
│
├── Compare two agents (classic vs new orchestrator, or any two agents)
│   ├── Generic (any 2 agents, any data source)
│   │   └── /cgo-ngo-agent-comparison
│   └── Fabric-specific (TableTalk vs Fabric Analyst, ContosoRetail dataset)
│       └── /cgo-ngo-fabric-comparison (calls /cgo-ngo-agent-comparison with pre-loaded context)
│
├── Look up CGO YAML patterns, best practices, flow wiring
│   └── /cgo-nl2query-patterns
│
├── Look up NL2Query patterns (DAX, adaptive TOPN, Power BI tools)
│   └── /ngo-nl2query-patterns
│
└── Build any New Generative Orchestrator agent (YAML, PAC CLI, Dataverse API, Workflows, Skills, file delivery)
    └── /copilot-studio-new-orchestrator
```

---

## Skills

### `/tabletalk-fabric-deploy`
**Deploy the CGO NL2Query agent (TableTalk with Fabric)**

What you need:
- Windows + PowerShell
- Power Platform environment (any channel)
- Copilot Studio license
- Power BI Pro or higher
- Az CLI + PAC CLI (or installable via winget/dotnet)
- Python (for dataset generation)
- Git (to clone Nico's repo)

What it does:
- Clones solution from [NicoPilot-dev/TableTalkWithFabric](https://github.com/NicoPilot-dev/TableTalkWithFabric)
- Creates ContosoRetail Power BI push dataset (13 tables, 500 rows each)
- Imports solution, configures agent
- Publishes and verifies

What it outputs: deployed CGO agent, 20 test questions, LEARNINGS.md with all IDs

---

### `/fabric-analyst-deploy`
**Deploy the NGO NL2Query agent (Fabric Analyst)**

What you need:
- Windows + PowerShell
- Power Platform environment with Copilot Studio (NGO requires the new orchestration experience — available in most regions)
- Copilot Studio license with **Anthropic models enabled**
- Power BI Pro or higher
- Az CLI + PAC CLI + Python
- No existing agent needed — skill creates the agent programmatically

What it does:
- Clones the nl2query-agent-build-eval repo (for the dataset script) if not already present
- Creates ContosoRetail Power BI push dataset via Python script (or reuses existing)
- Creates New Generative Orchestrator agent shell via PAC CLI + solution import
- Configures instructions + model via Dataverse API (PAC CLI push crashes on this architecture — see /copilot-studio-new-orchestrator Section 3)
- Adds 3 Power BI connector tools via CDP browser automation
- Adds full ContosoRetail schema skill and DAX patterns skill via Dataverse API
- Publishes, tests, takes screenshot

What it outputs: deployed NGO agent, 20 test questions, LEARNINGS.md, screenshot

Skip phases: checks LEARNINGS.md and skip-if-exists at every phase — safe to re-run.

---

### `/cgo-ngo-agent-comparison`
**Compare any two Copilot Studio agents (CGO and/or NGO)**

What you need:
- Paths to both agent local folders (or agent IDs to clone them)
- Agent test canvas URLs for CDP-based testing
- If testing NGO: CDP-ready browser profile (skill sets this up; user signs in once)
- Access to the agents' data sources (for grounded question generation)

What it does:
1. Explores agent configs and data source contents
2. Generates 20 grounded questions across 6 buckets (schema/architecture, goal-based, knowledge accuracy, edge cases, guardrails, multi-turn)
3. Sends each question to both agents via DirectLine (CGO) or CDP (NGO)
4. Scores responses on multiple graders (DAX accuracy, analytical depth, data transparency, general quality, etc.)
5. Generates interactive HTML comparison report
6. Outputs CGO starter test sets (CSV) for in-product Evaluation

What it outputs: comparison HTML report, scored results, CGO test CSVs, LEARNINGS.md, SKILL-ADDENDUM.md template

Auto-mode vs 2-step mode: auto runs end-to-end; 2-step shows question list + eval criteria for user approval before final tests.

Note: New Generative Orchestrator testing uses CDP browser; CGO testing uses DirectLine (no browser needed).

---

### `/cgo-ngo-fabric-comparison`
**Fabric-specific wrapper for the comparison skill**

Pre-loads: pre-validated expected answers from the June 2026 CAT baseline run, known divergences, DAX-specific test patterns, Fabric edge cases.

What you need: same as `/cgo-ngo-agent-comparison`, plus your own bot IDs and env ID (or use the example CDX values as a reference). LEARNINGS.md is read at start to skip manual ID entry.

What it outputs: same as comparison skill + updated baseline anchored to ContosoRetail dataset.

---

### `/cgo-nl2query-patterns`
**CGO YAML patterns, flow wiring, and best practices**

Reference skill — no deployment. Covers:
- settings.mcs.yml format for GenerativeAIRecognizer
- InvokeFlowTaskAction wiring
- Smart refresh pattern
- Output composition with adaptive cards
- _metadata table pattern for schema discovery

---

### `/ngo-nl2query-patterns`
**NL2Query / Power BI / DAX patterns for the New Generative Orchestrator**

Reference skill — NL2Query-specific. For general New Generative Orchestrator patterns (YAML, PAC CLI bugs, Dataverse API, Skills, CDP), see `/copilot-studio-new-orchestrator`. Covers:
- Adaptive TOPN (column-aware row budget estimation, 100K chars / 500 rows)
- DAX rules for Power BI push datasets (SUMX/FILTER, no active relationships)
- Power BI tool descriptions (domain-aware, for reliable tool selection)
- Schema probe pattern (TOPN(3) before any unfamiliar table)
- Generic-first instructions design for NL2Query agents

---

### `/copilot-studio-new-orchestrator`
**Comprehensive New Generative Orchestrator reference**

Reference skill — the authoritative guide for building any agent with the New Generative Orchestrator. Covers:
- YAML format (settings.mcs.yml, CLICopilotRecognizer, cliagent-1.0.0)
- PAC CLI bugs and workarounds (push crash, pull collapse, wipes tools, no skills CLI, /designer/ 404)
- Dataverse API PATCH pattern for updating agent config
- Tools: direct connectors + Workflows (and why legacy PA flows hit HTTP 500)
- Skills: Add-AgentSkill PowerShell function, Dataverse API POST, pac clone output format
- CDP browser automation for adding tools and skills
- Instructions design (generic-first, plain ASCII, domain-aware tool descriptions)
- File delivery (container → timestamped download link; SharePoint optional)
- LEARNINGS.md pattern for cross-session persistence
- New Generative Orchestrator vs CGO comparison table
- Platform gaps, CDX agenticruntime outage pattern, quick reference checklist

---

## LEARNINGS.md — cross-session persistence

Every deploy/comparison run writes a `LEARNINGS.md` to the working directory with:
- Discovered IDs (bot IDs, workspace, dataset, env)
- Session notes and timestamps
- Question sets (comparison skill)
- Scoring calibrations and divergences

Skills read this file at start and skip phases where IDs are already known. This makes re-runs fast and avoids re-discovering IDs.

## Using these skills

Each skill is a markdown instruction file. Load it into your AI assistant and follow its prompts.

To use with an AI assistant that supports a skills directory, copy the desired skill subfolder to wherever your tooling expects instruction files. No build step required — these are plain text.

---

## How Skills work in the New Generative Orchestrator

Skills are stored as `botcomponent` records (componenttype 9) in Dataverse with `kind: InlineAgentSkill`.

**When you clone:** `pac copilot clone` captures them as `translations/<schemaName>.skill.<name>.mcs.yml`

**When you create/update:** Use Dataverse API POST — `pac copilot push` and `pack` do NOT support `translations/` yet.

**When PAC CLI adds support:** Skills will be writeable via solution YAML files — no Dataverse API needed. The format is already defined and round-trips correctly through clone.

### Instructions vs Skills — the right split

| Put in **instructions** | Put in **skills** |
|---|---|
| Core identity and role | Dataset schema (table + column detail) |
| Dataset IDs (workspace, dataset) | DAX patterns for specific domains |
| Table names (list only) | Business rules and domain knowledge |
| Query protocol (TOPN, SUMX/FILTER) | Pre-compiled templates for common questions |
| Output and format rules | |

**Why this split:** Instructions apply on every turn (token overhead). Skills are retrieved selectively. Putting column-level detail and DAX patterns in skills keeps instructions short and focused.


