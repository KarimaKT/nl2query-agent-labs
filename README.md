# NL2Query Agent Labs for Copilot Studio

**Auto-deploy, compare, and learn from NL2Query agents on Power BI / Fabric — built with Copilot Studio.**

This repo contains skills, patterns, and tooling developed by the [Microsoft CAT team](https://aka.ms/cat) for building production-quality natural language to query (NL2Query) agents on Power BI and Microsoft Fabric using Copilot Studio.

It extends [Nico Sprotti's TableTalk with Fabric](https://github.com/NicoPilot-dev/TableTalkWithFabric) — the reference NL2Query agent for Copilot Studio — with automated deployment, an NGO architecture variant, side-by-side evaluation, and generalizable patterns for large data agents.

> **Terminology note:** "CGO" (Classic Generative Orchestration) and "NGO" (New Generative Orchestration) are terms coined by this team to distinguish the two Copilot Studio orchestration architectures. They are not official Microsoft product terminology. See [Glossary](#glossary).

---

## What's in this repo

This is **four things in one**:

### 1. TableTalk with Fabric — auto-deploy + test (CGO)

[TableTalk with Fabric](https://github.com/NicoPilot-dev/TableTalkWithFabric) is a production-ready NL2Query agent by Nico Sprotti that generates DAX, queries your Fabric/Power BI semantic model, charts results, and shows its reasoning. It ships as a Copilot Studio solution zip.

This repo adds:
- **Automated deployment** of TableTalk into any Power Platform environment via the `/tabletalk-fabric-deploy` skill
- **ContosoRetail sample dataset** — a realistic 13-table Power BI push dataset (500 rows/table) with a built-in business story: underperforming West region, collapsing email ROI, high-margin Beauty, two bad suppliers, VIP LTV patterns
- **20 test questions** with expected answers for validating the deployment

### 2. Fabric Analyst — NGO architecture variant

A second NL2Query agent built with the **new Copilot Studio orchestrator** (CLICopilotRecognizer, cliagent-1.0.0) over the same ContosoRetail dataset. No topics or Power Automate flows — only Tools, Skills, and a reasoning loop.

**Generic-first design:** Instructions contain only tool routing, DAX rules, and output format — nothing domain-specific. All schema and domain knowledge lives in Skills. This means the same agent definition works against any Power BI dataset: swap the Skills for a different schema without touching instructions or agent config. This is a deliberate contrast with the CGO approach, where dataset-specific context often lives in the system prompt.

The `/fabric-analyst-deploy` skill deploys this agent fully programmatically (PAC CLI + Dataverse API — no manual UI steps), using the same ContosoRetail dataset as TableTalk so the two agents can be compared directly.

### 3. Agent comparison — CGO vs NGO, or any two agents

Two comparison skills:

- **`/cgo-ngo-agent-comparison`** — Generic: compare any two Copilot Studio agents. Explores agent configs and data sources, generates grounded questions across 6 test buckets, runs them against both agents, scores with multiple graders, and produces an interactive HTML report.
- **`/cgo-ngo-fabric-comparison`** — Fabric-specific wrapper pre-loaded with ContosoRetail expected answers and a 19-question baseline from the June 2026 CAT evaluation run.

From the June 2026 run: CGO scored 94/95 (A+), NGO scored 84/95 (B, adjusted ~88/95). Both agents produced numerically identical answers on 7+ questions. Key divergence: marketing channel ROI trend (different DAX approaches to time-series aggregation).

### 4. NL2Query + NGO patterns and skills

**Reference skills** covering everything we learned building and evaluating these agents:

- **`/ngo-nl2query-patterns`** — The definitive NGO reference: YAML format, PAC CLI bugs, Dataverse API workarounds, CDP browser automation, instructions design, skills via Dataverse API, CDX outage pattern, CGO vs NGO comparison table.
- **`/cgo-nl2query-patterns`** — CGO: YAML format, flow wiring, smart refresh, _metadata table pattern, output composition.
- **`/copilot-studio-new-orchestrator`** — NGO-specific: settings.mcs.yml format, known bugs, /designer/ URL gotcha, Early Release requirement.

#### NGO Skills — a novel capability

There is currently no public documentation or example of programmatically adding Skills to an NGO agent. This repo documents the full pattern:

1. Skills are stored as `botcomponent` records (componenttype 9, `kind: InlineAgentSkill`) in Dataverse
2. `pac copilot clone` captures them in `translations/<schemaName>.skill.<name>.mcs.yml`
3. `pac copilot push/pack` do NOT yet support `translations/` — Dataverse API POST is the only automated write path
4. Once PAC CLI adds support, skills become first-class YAML files in the agent solution

The `/ngo-nl2query-patterns` and `/fabric-analyst-deploy` skills both contain the complete `Add-AgentSkill` PowerShell function.

---

## Repo structure

```
skills/
  README.md                          ← decision guide, prerequisites, usage
  tabletalk-fabric-deploy/SKILL.md   ← deploy TableTalk (CGO) + ContosoRetail
  fabric-analyst-deploy/SKILL.md     ← deploy Fabric Analyst (NGO) + ContosoRetail
  cgo-ngo-agent-comparison/SKILL.md  ← compare any two agents
  cgo-ngo-fabric-comparison/SKILL.md ← Fabric-specific comparison (pre-loaded)
  cgo-nl2query-patterns/SKILL.md     ← CGO YAML patterns reference
  ngo-nl2query-patterns/SKILL.md     ← NGO patterns, bugs, Dataverse API
  copilot-studio-new-orchestrator/SKILL.md ← NGO format + gotchas

dataset/
  build_contoso_dataset.py           ← generates ContosoRetail push dataset
```

These skills are designed for [Clawpilot](https://aka.ms/clawpilot) — invoke with `/skill-name` in chat.

---

## Quick start

### Deploy TableTalk (CGO) + ContosoRetail dataset

```
/tabletalk-fabric-deploy
```

**Requires:** Windows + PowerShell, Power Platform environment, Copilot Studio license, Power BI Pro, Az CLI + PAC CLI + Python.

The skill clones Nico's repo, generates the ContosoRetail dataset, imports the solution, updates agent instructions with your dataset IDs, publishes, and tests.

### Deploy Fabric Analyst (NGO)

```
/fabric-analyst-deploy
```

**Extra requirement:** Copilot Studio on **Early Release channel** (NGO requires Early Release as of mid-2026) + Anthropic models enabled.

The skill creates the agent programmatically — no manual UI step needed.

### Compare the two agents

```
/cgo-ngo-fabric-comparison
```

Runs both agents against 19 questions, scores with multiple graders, and produces an interactive HTML comparison report.

### Compare any two agents

```
/cgo-ngo-agent-comparison
```

Works with any two Copilot Studio agents (CGO or NGO). Provide agent paths and canvas URLs — the skill explores configs, generates grounded questions, tests, and reports.

### Install skills locally

Clone or download this repo — the skills are plain markdown files, no install needed:

```bash
git clone https://github.com/KarimaKT/nl2query-agent-labs
```

Point your AI assistant at the `skills/` folder, or copy individual skill subfolders wherever your tooling expects them. No build step, no dependencies.

---

## ContosoRetail dataset

A synthetic 13-table Power BI push dataset built for NL2Query evaluation. Deterministically generated (seed=42) so results are reproducible across deployments.

**Business story baked in:**
- West/Southwest regions underperform vs Midwest/North
- Email marketing ROI declining since 2024; Social ROI surging
- Beauty category: ~60% gross margin (highest)
- Suppliers SUP03 (59.4% on-time) and SUP07 (66.7% on-time) are reliability risks
- VIP customers: highest LTV (~$5,216 avg), At-Risk: highest revenue volume

This story makes the evaluation questions non-trivial — the right answers require multi-step DAX, cross-table joins (no active relationships — push dataset), and time-series aggregation.

```bash
pip install requests faker
python dataset/build_contoso_dataset.py <workspace_id> [tenant_id]
# Outputs: dataset_id.txt
```


---

## Data volume handling: CGO vs NGO

One of the most instructive architectural differences between CGO (TableTalk) and NGO (Fabric Analyst) is how they handle result size limits. Understanding this helps you build better agents on either architecture.

### CGO approach — enforce limits in the flow

TableTalk truncates results **in the Power Automate flow**, before the model ever sees the data:

```
ExecuteDatasetQuery action
  → success scope: take first MIN(100 rows, 100,000 chars)
  → failure scope: return error message
```

The model always receives a predictable, bounded payload. It never has to reason about data volume. The tradeoff: you lose rows silently and the agent doesn't know it's seeing a truncated view.

The flow description also instructs the model to use `SUMMARIZECOLUMNS` (aggregations return far fewer rows than raw table scans), so in practice most queries never hit the cap.

### NGO approach — reason about limits in the instructions

NGO calls the Power BI connector directly — no flow intermediary. The model is responsible for structuring its own queries to fit within the context window. This is more powerful (no hidden truncation) but requires explicit guidance in the agent's instructions.

The Fabric Analyst agent uses a **column-aware adaptive TOPN** pattern:

```
1. Schema probe: EVALUATE TOPN(3, tablename)
   → learn column names and typical value widths

2. Identify selected columns
   → only the columns your actual query projects

3. Per-column width estimate from probe samples
   → sum widths of selected columns only (not full row width)
   → a 3-column projection is much narrower than a 15-column table

4. Calculate N
   N = floor(target_chars / estimated_row_width), clamped to [50, 200]
   target_chars default = 100,000 (adjustable per model context size)

5. Apply: EVALUATE TOPN(N, ...)

6. Truncation detection
   → if results look incomplete, halve N or switch to aggregation
```

**Why this is better than a fixed cap:**
- A query selecting 3 ID + numeric columns can safely return 200 rows
- A query selecting 8 text-heavy columns should stop at 50
- The model makes the call based on actual data shape, not a static threshold

### Comparison

| Concern | CGO (TableTalk) | NGO (Fabric Analyst) |
|---|---|---|
| Where limit is enforced | Power Automate flow (100 rows / 30K chars) | Agent reasoning loop (adaptive TOPN) |
| Silent truncation | Yes — model doesn't know | No — model controls the limit |
| Per-column awareness | No | Yes — estimates from selected columns only |
| Model context adaptation | No | Yes — target_chars adjustable per model |
| DAX strategy guidance | In flow description | In agent instructions |
| Requires model reasoning | No | Yes — instructions must be explicit |
| Consistency | High (enforced) | Depends on instruction quality |

### What this means for builders

- **CGO** is simpler and more consistent out of the box — the flow enforces safety. Good for production deployments where predictability matters more than control.
- **NGO** gives the model full visibility into results with no hidden truncation — better for analytical depth, but only if the instructions are well-crafted. Under-specified instructions lead to unpredictable query sizes.
- The adaptive TOPN pattern can be documented in the agent's `schema-definitions` skill so it applies consistently across all queries without cluttering the top-level instructions.
---

## Glossary

| Term | Meaning |
|---|---|
| **CGO** | Classic Generative Orchestration — Copilot Studio agents using `GenerativeAIRecognizer` + `default-2.1.0` schema, with topics and Power Automate flows. The stable, well-documented architecture. *(Our term)* |
| **NGO** | New Generative Orchestration — Copilot Studio agents using `CLICopilotRecognizer` + `cliagent-1.0.0` schema, with only Tools and Skills. Available on Early Release channel as of mid-2026. *(Our term)* |
| **NL2Query** | Natural Language to Query — agents that translate user questions into database queries (DAX in this case) and synthesize answers from results |
| **Push dataset** | A Power BI dataset type where rows are pushed via REST API rather than scheduled refresh from a source. No active relationships — requires SUMX(FILTER()) for cross-table joins |
| **PAC CLI** | Power Platform CLI — `pac.exe`, used for Copilot Studio agent management (clone, push, publish) |
| **Dataverse API** | REST API for Power Platform's underlying database — used to configure agents and add skills when PAC CLI has limitations |
| **TOPN(3) protocol** | DAX exploration pattern: run `EVALUATE TOPN(3, tablename)` before aggregating an unfamiliar table to discover columns and sample values |

---

## Known limitations and PAC CLI bugs

See `/ngo-nl2query-patterns` for the full list. Key ones:

| Bug | Workaround |
|---|---|
| `pac copilot push` crashes on cliagent-1.0.0 (ArgumentOutOfRangeException) | Use Dataverse API PATCH for agent config |
| `pac copilot push` wipes manually-added tools | NEVER push if agent has manual tools; keep all tools in YAML |
| `pac copilot pack` rejects `translations/`, `actions/`, `workflows/` | These are write-only via Dataverse API currently |
| Skills have no PAC CLI commands | Use Dataverse API POST (documented in `/ngo-nl2query-patterns`) |
| `/agents/designer/<botId>` URL 404s | Use `/agents/<botId>` |

---

## Credits

- **[TableTalk with Fabric](https://github.com/NicoPilot-dev/TableTalkWithFabric)** — Nico Sprotti ([GitHub](https://github.com/NicoPilot-dev)) — the reference CGO NL2Query agent that this project builds on and compares against
- **[Microsoft CAT team](https://aka.ms/cat)** — Fabric Analyst (NGO), ContosoRetail dataset, comparison framework, skills library

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

*CGO and NGO are working terms coined by the Microsoft CAT team to describe the two Copilot Studio orchestration architectures. They are not official product names.*



