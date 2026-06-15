# Copilot Studio Fabric NL2Query — Skill Library

Skills for building, deploying, comparing, and evaluating NL2Query agents on Power BI / Fabric using Copilot Studio.

Built by the Microsoft CAT team. CGO reference agent (TableTalk with Fabric) by [Nico Sprotti](https://github.com/NicoPilot-dev/TableTalkWithFabric).

---

## Decision guide

```
What do you want to do?
│
├── Deploy a CGO (classic orchestration) NL2Query agent
│   └── /tabletalk-fabric-deploy
│
├── Deploy an NGO (new orchestration) NL2Query agent  
│   └── /fabric-analyst-deploy
│
├── Compare two agents (CGO vs NGO, or any two agents)
│   ├── Generic (any 2 agents, any data source)
│   │   └── /cgo-ngo-agent-comparison
│   └── Fabric-specific (TableTalk vs Fabric Analyst, ContosoRetail dataset)
│       └── /cgo-ngo-fabric-comparison (calls /cgo-ngo-agent-comparison with pre-loaded context)
│
├── Look up CGO YAML patterns, best practices, flow wiring
│   └── /cgo-nl2query-patterns
│
├── Look up NGO YAML patterns, PAC CLI bugs, Dataverse API workarounds
│   └── /ngo-nl2query-patterns
│
└── Understand NGO agent format, settings.mcs.yml, gotchas
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
- Creates ContosoRetail Power BI push dataset (or reuses existing)
- Creates NGO agent shell via PAC CLI + solution import
- Configures instructions + model via Dataverse API (avoids PAC CLI push bug)
- Adds 3 Power BI tools via CDP browser automation. Adds skills via Dataverse API (no browser needed)
- Publishes, tests, screenshots

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

Note: NGO testing uses CDP browser; CGO testing uses DirectLine (no browser needed).

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
**NGO patterns, PAC CLI bugs, Dataverse API workarounds**

Reference skill — no deployment. Covers:
- CLICopilotRecognizer + cliagent-1.0.0 YAML format
- All known PAC CLI bugs and safe workarounds
- Dataverse API PATCH pattern (the only safe config path)
- Direct connector tools (not PA flows)
- CDP browser automation for Tools and Skills
- Instructions design for NL2Query reasoning loop
- CDX agenticruntime outage pattern (how to distinguish from real errors)

---

### `/copilot-studio-new-orchestrator`
**NGO agent format, settings, gotchas, /designer/ URL fix**

Reference skill — covers: YAML schema, known UI bugs (/designer/ URL 404), PAC CLI limitations.

---

## LEARNINGS.md — cross-session persistence

Every deploy/comparison run writes a `LEARNINGS.md` to the working directory with:
- Discovered IDs (bot IDs, workspace, dataset, env)
- Session notes and timestamps
- Question sets (comparison skill)
- Scoring calibrations and divergences

Skills read this file at start and skip phases where IDs are already known. This makes re-runs fast and avoids re-discovering IDs.

## Installing skills locally

Skills in this folder are ready to use with Clawpilot. To install:

```powershell
# Copy to Clawpilot m-skills directory
Get-ChildItem "C:\src\Fabric\skills" -Directory | ForEach-Object {
    $dest = "$env:USERPROFILE\.copilot\m-skills\$($_.Name)"
    if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
    Copy-Item "$($_.FullName)\SKILL.md" "$dest\SKILL.md" -Force
    Write-Host "Installed: $($_.Name)"
}
```

After installing, invoke any skill by typing `/skill-name` in Clawpilot chat.

---

## How skills work in NGO solutions

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

