---
name: "cgo-ngo-fabric-comparison"
description: "Compare the CGO NL2Query agent (TableTalk with Fabric) against the NGO NL2Query agent (Fabric Analyst) over the ContosoRetail Power BI dataset. Pre-loads validated expected answers, known divergences, DAX-specific test patterns, and Fabric architecture tests. Calls the generic /cgo-ngo-agent-comparison skill with Fabric context pre-configured."
---

# Fabric NL2Query Agent Comparison Skill

This skill is a pre-configured invocation of the generic `/cgo-ngo-agent-comparison` skill, specialized for the Fabric NL2Query use case: comparing the CGO agent (TableTalk with Fabric) against the NGO agent (Fabric Analyst) over the ContosoRetail Power BI push dataset.

**Invoke the generic skill first** (`/cgo-ngo-agent-comparison`), then apply the Fabric context below as overrides and pre-loaded data.

---

## Pre-configured inputs

These are **example values from the original CAT CAT CDX deployment**. Replace them with your own agent and environment IDs. The skill will ask for these if not pre-loaded; you can also store them in your working directory LEARNINGS.md file (see below).

To find your values:
- **envId**: from your Copilot Studio environment URL
- **botId**: from `pac copilot list` or the agent URL
- **workspaceId / datasetId**: from Power BI workspace settings

```Agent 1: CGO — TableTalk with Fabric
  Bot ID: 3a1ef82e-a93a-4bf7-bf9a-dbfebc8fc421
  Local path: C:\src\Fabric\agent\TableTalk with Fabric\
  Type: CGO (GenerativeAIRecognizer, default-2.1.0)
  Model: Opus 4.8
  Tools: Send DAX Query (PA flow), Refresh Dataset (PA flow), Chart Adaptive Card (topic)
  Data: Power BI push dataset — ContosoRetail, WorkspaceID f9b7b05b-44c8-4740-9372-b9a958007c63

Agent 2: NGO — Fabric Analyst
  Bot ID: d01d7579-bf47-4da7-b751-22a419ade844
  Local path: C:\src\Fabric\fabric-analyst\Fabric Analyst\
  Type: NGO (CLICopilotRecognizer, cliagent-1.0.0)
  Model: Opus 4.8
  Tools: Run a query against a dataset (direct connector), Run a json query against a dataset, OneDrive for Business Create file
  Skills: schema-definitions, dax-patterns-customer, dax-patterns-marketing, dax-patterns-operations, python-pseudocode
  Data: Same Power BI push dataset — ContosoRetail, DatasetID 3edbaf84-2fe8-47d8-b4c8-97bd8d6c806b

Environment: 61453fde-f312-e19f-b879-a2dfa518e914 (CDX Contoso Group)
Output folder: C:\src\Fabric\comparison\<timestamp>
```


### Load from LEARNINGS.md (skip manual entry if file exists)

Before running, check for a LEARNINGS.md in your working directory:
```powershell
$learnFile = "$outputFolder\LEARNINGS.md"
if (Test-Path $learnFile) {
    $learnings = Get-Content $learnFile -Raw
    if ($learnings -match 'cgoBotId:\s*(\S+)') { $cgoAgent.BotId = $Matches[1] }
    if ($learnings -match 'ngoBotId:\s*(\S+)') { $ngoAgent.BotId = $Matches[1] }
    if ($learnings -match 'envId:\s*(\S+)') { $envId = $Matches[1] }
    if ($learnings -match 'workspaceId:\s*(\S+)') { $workspaceId = $Matches[1] }
    if ($learnings -match 'datasetId:\s*(\S+)') { $datasetId = $Matches[1] }
    Write-Host "Loaded IDs from $learnFile"
}
```

## Pre-validated expected answers (use as Type C knowledge tests)

Both agents confirmed these on independent runs (June 2026). Use as `expectedResponse` in test CSVs and as compare-meaning grader inputs.

| Question | Expected Answer | Confidence |
|---|---|---|
| "Which customer segment drives the most revenue?" | At-Risk: $37,099 (136 orders), Regular: $34,945, New: $33,994, VIP: $27,163 | High — both agents agreed |
| "Are there any supplier reliability issues?" | Supplier C (SUP03): 59.4% on-time, quality 4.91/10. Supplier G (SUP07): 66.7% on-time, quality 4.73/10. Both handle ~$1.84M PO volume. | High |
| "Which product categories have the highest profit margins?" | Beauty: 59.8%, Home & Garden: 45.1%, Apparel: 40.1%, Sports & Outdoors: 35.1%, Electronics: 17.3% | High |
| "What is the customer lifetime value by segment?" | VIP: avg $5,216.14 (100 customers, $521K total, 77% of all LTV). Regular: $952.70. At-Risk: $220.51. New: $107.07. | High |
| "Which sales region has the weakest revenue performance?" | Southwest: $23,320 (94 orders, $248.09 avg). Midwest strongest: $29,080. | High |
| "Show inventory stockout patterns" | Sports & Outdoors: 19% stockout rate. 8% overall. ST20 worst store at 20.8%. | High |
| "Which campaigns generated the highest revenue lift?" | Win-Back (Social): $1.23M net lift, 2.97 ROI. Loyalty Boost (Social): $1.12M, 3.14 ROI (best ROI). | High |

---

## Known divergences (flag in comparison, do not use as expected answer)

These questions produced materially different answers between CGO and NGO. Both cannot be right — warrants manual DAX verification.

| Question | CGO answer | NGO answer | Likely cause |
|---|---|---|---|
| Q3: "Compare marketing channel ROI over time" | Email ROI improving: 1.64x (2023) → 2.14x (2025) | Email ROI collapsing: 2.02x → -0.03x in 2025 (destroying value) | Different DAX approach to time-series aggregation |
| Q14: "Show top and bottom performing employees by quota attainment" | Found data — 17/71 "Exceeds", named specific employees | No quota columns exist — refused to fabricate | CGO may have used performance_rating as undisclosed proxy |

---

## Fabric-specific test patterns

### Type A — Single tool call (Architecture)

These questions should trigger EXACTLY one tool call:

| Question | Expected tool | Expected result |
|---|---|---|
| "Refresh the dataset" | CGO: Refresh Dataset flow / NGO: Refresh a dataset | Refresh triggered, status returned |
| "Show me the first 3 rows of dim_customers" | CGO: Send DAX Query / NGO: Run a query | `EVALUATE TOPN(3, dim_customers)` result |
| "How many tables do you have access to?" | Neither — should answer from instructions | 13 tables listed |

### Type B — Goal-based / chained

These require multiple tool calls and synthesis:

| Question | Expected chain | Min tool calls |
|---|---|---|
| "What is the customer lifetime value by segment, and which segment should we prioritize for retention investment?" | Schema discovery → CLV aggregation → segment analysis → synthesis | 2 |
| "Which category has the worst return rate and the best margin — is there a conflict?" | Return rate query → margin query → synthesis comparing both | 2 |
| "Give me a comprehensive executive summary of the business" | 5–8 queries across multiple tables → full synthesis | 5+ |

### Type C — Knowledge / retrieval (DAX accuracy)

For NL2Query agents, "knowledge" is the dataset. The citation equivalent is: did the agent use the right table and column? Did it self-correct when DAX failed?

| Question | Expected answer | Expected DAX pattern |
|---|---|---|
| "Revenue by customer segment" | At-Risk $37,099... (see pre-validated above) | SUMX(FILTER()) — no active relationships in push dataset |
| "Supplier on-time delivery rate" | SUP03: 59.4%, SUP07: 66.7%... | COUNTROWS(FILTER(fact_supplier_performance, on_time_flag = 'Yes')) / COUNTROWS() |
| "Marketing ROI by channel 2023–2025" | Social: 1.8x→4.12x. Email: 3.02x→-0.03x (NGO) or improving (CGO) — FLAG DIVERGENCE | SUMMARIZECOLUMNS(channel, year, AVERAGE(roi)) |

### DAX-specific quality signals (add to scoring rubric)

For each response, also note:
- **TOPN(3) protocol**: Did agent run `EVALUATE TOPN(3, tablename)` before aggregating an unfamiliar table? (Yes = good practice)
- **SUMX/FILTER for joins**: Did agent use `SUMX(FILTER(fact_table, fact_table[key] = dim_table[key]))` for cross-table joins? (Yes = correct for push dataset with no active relationships)
- **Self-correction**: Did agent detect implausible results (e.g. equal values across all groups) and retry with a corrected approach?
- **Data transparency**: Did agent disclose when expected data columns don't exist, rather than fabricating?

---

## Fabric-specific edge cases (Type E)

| Question | Expected behavior |
|---|---|
| "Write a row to dim_customers" | SHOULD REFUSE — agent is read-only |
| "Give me data from the CRM system" | SHOULD REFUSE or clarify — only ContosoRetail dataset available |
| "What happened in Q3 2022?" | Should note data only covers 2023–2025 |
| "Compare our performance to competitors" | Should refuse or acknowledge no external benchmark data |
| "Generate a chart for me" (in NGO) | Should offer HTML report to OneDrive, NOT try to render inline |
| "Generate a chart for me" (in CGO) | Should invoke Chart Adaptive Card topic and render inline |

---

## Fabric-specific multi-turn sequences (Type F)

```
Sequence 1:
  Turn 1: "Which customer segment drives the most revenue?"
  Turn 2: "Now break that down by region. Which region has the highest VIP concentration?"
  Test: Did Turn 2 build on Turn 1 context (segment = At-Risk) or re-run from scratch?

Sequence 2:
  Turn 1: "Which suppliers have reliability issues?"
  Turn 2: "What categories do those suppliers serve? Are our high-margin categories at risk?"
  Test: Did Turn 2 connect supplier IDs from Turn 1 to category data?

Sequence 3 (NGO multi-turn + file delivery):
  Turn 1: "Give me a revenue analysis by segment and region"
  Turn 2: "Save that as an HTML report to my OneDrive"
  Test: Did agent save the file and return a path?
```

---

## Previous run results (June 8, 2026 baseline)

Use these as comparison anchor when re-running:

| Metric | CGO (TableTalk) | NGO (Fabric Analyst) |
|---|---|---|
| Score | 94/95 (A+) | 84/95 (B, adj ~88/95) |
| Pass rate | 19/19 | 19/19 (2 anomalies from test harness) |
| Avg time/question | 60–180s | 36–100s (avg 48s) |
| Self-correction on Q2 | 7 DAX iterations | Not observed |
| Reasoning visibility | Hidden | Visible inline 14/19 |
| Charts in chat | Adaptive Cards ✅ | Blocked ❌ |

Q4 and Q15 NGO scored 2/5 due to test harness capturing intermediate reasoning instead of final answer — estimated true score 4/5 each.

---

## Output additions for Fabric use case

In addition to generic skill outputs, also write:
- `C:\src\Fabric\comparison\` — update with new run results
- A new dated comparison report alongside the existing `cgo-vs-ngo-comparison.html`
- Starter test CSVs for use in CGO Copilot Studio in-product Evaluation
- Custom grader specs for the pre-validated knowledge questions


