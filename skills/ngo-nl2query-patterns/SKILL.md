---
name: "ngo-nl2query-patterns"
description: "NL2Query / Power BI specific patterns for agents built on the New Generative Orchestrator (CLICopilotRecognizer, cliagent-1.0.0). Covers adaptive TOPN, DAX rules for push datasets, Power BI tool descriptions, truncation detection, and generic-first NL2Query design."
---

> For general New Generative Orchestrator patterns (YAML format, PAC CLI bugs, Dataverse API, Skills, CDP,
> file delivery), see `/copilot-studio-new-orchestrator`.

# NL2Query Patterns — Power BI / New Generative Orchestrator

Patterns specific to NL2Query agents targeting Power BI push datasets, built on the New Generative Orchestrator.

---

## 1. Power BI Tool Descriptions

Domain-aware tool descriptions significantly improve tool selection accuracy in the reasoning loop.
Use these as the `modelDescription` in your action or connector tool definitions.

| Tool | Recommended modelDescription |
|------|-------------------------------|
| Run a query against a dataset | Executes a DAX EVALUATE statement against a Power BI push dataset. Use for all data retrieval: counts, aggregations, slices, and row-level queries. Input: workspaceId (GUID), datasetId (GUID), daxQuery (string starting with EVALUATE). Returns plain text rows. |
| Run a json query against a dataset | Executes a structured JSON query (Power BI REST query format) against a dataset. Use when DAX is not appropriate or for simple top-N row fetches with column projection. |
| Refresh a dataset | Triggers a manual refresh of a Power BI dataset. Do NOT call unless explicitly asked — data is maintained on an external schedule. Calling this unexpectedly will confuse users. |

---

## 2. Generic-First Design for NL2Query

The new orchestrator agent is designed to be **use-case agnostic at the instruction level**:

- **Instructions** contain: tool routing, DAX rules, output format, adaptive TOPN logic, dataset IDs
- **Skills** contain: schema (table names, column types, join keys), domain context, DAX patterns for known question types

**Benefit:** The same agent definition deploys against any Power BI dataset — swap Skills for a different
schema without touching instructions or agent config.

### What belongs where

| Content | Instructions | Skill |
|---|---|---|
| Tool routing (which tool for what) | Yes | |
| Dataset IDs (workspaceId, datasetId) | Yes | |
| DAX protocol rules (TOPN, SUMX/FILTER, self-correct) | Yes | |
| Output format rules | Yes | |
| Table names (list only) | Yes | Yes (with column detail) |
| Column names, types, sample values | | Yes |
| Business rules specific to domain | | Yes |
| Known DAX patterns for domain questions | | Yes |
| Pre-validated answers for testing | | Yes (test skills only) |

---

## 3. NL2Query Instructions Template

```
You are a Power BI NL2Query assistant.

## Data Context
WorkspaceID: <guid>
DatasetID: <guid>
Tables: [comma-separated list]
Note: Do NOT list column names — discover them at runtime via TOPN.

## Query Protocol
1. Schema probe: Before aggregating an unfamiliar table, run EVALUATE TOPN(3, tablename)
2. Cross-table joins: Use SUMX(FILTER()) — push datasets have no active relationships
3. Self-correction: If a DAX query returns an error or implausible result, reformulate and retry up to 3 times
4. Date filtering: Use CALENDAR or Date table — never filter on string date columns

## Adaptive TOPN
[Include the TOPN estimation block from Section 4 here]

## Operational Rules
- Do NOT call RefreshDataset. Data is on an external schedule.
- Never output raw DAX code blocks in the chat response.
- Synthesize findings with specific numbers, percentages, and trends.
- If unsure of column name, run TOPN(3) to discover — do not guess.

## Output Format
- Lead with the direct answer.
- Follow with supporting metrics.
- End with 3 suggested follow-up questions.
```

---

## 4. Adaptive TOPN — Column-Aware Row Budget

**The problem:** The Power BI REST API can return up to 100K rows. Context windows are finite. A 15-column
table with text fields produces 400+ chars per row — 100 rows already blows the budget. A 3-column
projection of the same table could safely fit 500 rows. Hardcoding TOPN(50) is too conservative for narrow
queries; omitting TOPN entirely risks truncation or context exhaustion for wide ones.

**The solution:** Estimate N from the schema probe, adjusted for the *specific columns your query selects*.

```
Step 1 — Schema probe (always run first on unfamiliar tables)
  EVALUATE TOPN(3, tablename)
  Observe: column names, data types, sample value widths

Step 2 — Identify projected columns
  Note which columns your query will SELECT.
  If fetching all columns, use all. If projecting a subset, use those only.

Step 3 — Per-column width estimate from probe data
  Short IDs / codes ("SUP03", "East"):          ~8 chars
  Numeric values ("59.4", "37099.50"):           ~10 chars
  Names / category labels ("Beauty", "At-Risk"): ~15 chars
  Dates ("2024-03-15"):                          ~12 chars
  Free text / descriptions:                      ~50-100 chars

Step 4 — Row width
  estimated_row_width = sum of avg_char_width for selected columns
  Add ~10% for separators and formatting overhead

Step 5 — Calculate N
  target_chars = 100000   (default; adjust per model — see table below)
  N = floor(target_chars / estimated_row_width)
  Clamp N to [50, 500]

  Examples:
    3 cols x 20 chars avg  ->  row = 60   ->  N = 500 (clamp to 200)
    8 cols x 40 chars avg  ->  row = 320  ->  N = 93
    5 text cols x 80 chars ->  row = 400  ->  N = 75
    15 cols x 25 chars avg ->  row = 375  ->  N = 80

Step 6 — Apply
  EVALUATE TOPN(N, SUMMARIZECOLUMNS(col1, col2, ...), sort_col, ASC)
  or for raw row fetch:
  EVALUATE TOPN(N, tablename, sort_col, ASC)
```

### target_chars by model context size

| Model | target_chars |
|---|---|
| Unknown / default | 30,000 |
| Claude Opus 4.x (200K context) | 50,000-80,000 |
| GPT-4o (128K context) | 40,000-60,000 |
| Small / limited models | 15,000-20,000 |

---

## 5. DAX Rules for Push Datasets

Push datasets have no active relationships between tables. These rules apply universally.

| Pattern | Use case |
|---------|----------|
| `EVALUATE TOPN(3, 'TableName')` | Schema discovery, column validation |
| `EVALUATE SUMMARIZECOLUMNS('Dim'[Col], "Metric", [Measure])` | Standard aggregation |
| `EVALUATE SUMX(FILTER('Fact', RELATED('Dim'[Key]) = "value"), 'Fact'[Amount])` | Cross-table aggregation — no active relationships |
| `VAR _base = [Measure] RETURN DIVIDE(_base, [Total])` | Ratio / percentage calculation |
| `EVALUATE ROW("Result", CALCULATE([Measure], 'Date'[Year]=2025))` | Single-cell time-filtered result |

**Never use:** `RELATEDTABLE()`, implicit relationships, `USERELATIONSHIP()` on a non-existent relationship.

**Always probe first:** Run `EVALUATE TOPN(3, 'TableName')` before any aggregation on an unfamiliar table.
The schema probe confirms column names, data types, and whether SUMX or SUMMARIZECOLUMNS is appropriate.

---

## 6. Truncation Detection

If results look incomplete — totals inconsistent, list suspiciously short, count lower than a prior
`COUNTROWS` check — treat as truncated.

**Detection signals:**
- Numeric totals that do not add up across rows
- A "top N" list that ends at a suspiciously round number
- `COUNTROWS` returning more rows than the query returned

**Response:**
1. Retry with halved N
2. Switch to `SUMMARIZECOLUMNS` aggregation instead of raw row fetch
3. Add a `COUNTROWS` probe to determine true table size before re-running

---

## 7. Schema Probe Pattern

Run before any aggregation on an unfamiliar table:

```dax
EVALUATE TOPN(3, 'TableName')
```

Observe from the result:
- Column names (exact spelling — DAX is case-sensitive in some environments)
- Data types (text vs numeric vs date changes which DAX functions apply)
- Sample value widths (feeds into adaptive TOPN N estimation in Section 4)
- Whether a Date / Calendar table exists for time filtering
