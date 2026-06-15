---
name: "cgo-nl2query-patterns"
description: "Design patterns, YAML syntax, and best practices for building NL2Query agents with Classic Generative Orchestration (CGO) in Copilot Studio. Covers topics, conversation variables, flow wiring, smart refresh, output composition, and the _metadata table pattern."
---

# CGO NL2Query Agent — Design Patterns

Classic Generative Orchestration (CGO) uses `recognizer: kind: GenerativeAIRecognizer` and `template: default-2.1.0`. This is the well-supported, stable orchestrator as of mid-2026. Topics route user messages. Power Automate flows are wired as `InvokeFlowTaskAction` inside topic `AdaptiveDialog` nodes.

---

## settings.mcs.yml Format (CGO)

```yaml
displayName: My Agent
schemaName: myprefix_MyAgent
configuration:
  settings:
    GenerativeActionsEnabled: true
  recognizer:
    kind: GenerativeAIRecognizer
  gPTSettings:
    defaultSchemaName: myprefix_MyAgent.gpt.default
  aISettings:
    useModelKnowledge: true
    isFileAnalysisEnabled: false
    contentModeration: Low
template: default-2.1.0
language: 1033
```

**Do NOT use** `SmartTaskCompletionEnabled` — that is the deprecated Enhanced Task Completion flag.

---

## agent.mcs.yml Format (CGO)

```yaml
kind: GptComponentMetadata
displayName: My Agent
instructions: |-
  Your system prompt here.
  # Data #
  workspaceid <uuid>
  datasetid <uuid>
  tables: table1, table2, table3
gptCapabilities:
  webBrowsing: false
  codeInterpreter: false
aISettings:
  model:
    kind: ExperimentalModels
    modelNameHint: Opus48
```

Keep instructions minimal — table names only, no column lists at scale.

---

## Action (Tool) File Format

```yaml
mcs.metadata:
  componentName: Execute DAX Query
kind: TaskDialog
inputs:
  - kind: AutomaticTaskInput
    propertyName: text
    name: DaxQuery
    description: The DAX query to execute.
  - kind: AutomaticTaskInput
    propertyName: text_1
    name: workspaceid
    description: Power BI workspace ID.
  - kind: AutomaticTaskInput
    propertyName: text_2
    name: datasetid
    description: Power BI dataset ID.
modelDisplayName: Execute DAX
modelDescription: Executes a DAX query and returns results as plain text.
outputs:
  - propertyName: daxqueryresults
action:
  kind: InvokeFlowTaskAction
  flowId: <your-flow-guid>
  connectionProperties:
    $kind: ConnectionProperties
    mode: Invoker
outputMode: All
```

**Critical:** `mode: Invoker` is non-negotiable for enterprise — queries run as the signed-in user, so Power BI RLS applies automatically. Never use a fixed service account.

**Do not add `defaultValue`** to `AutomaticTaskInput` — this causes publish failures.

---

## System Prompt Design (3 rules)

**Rule 1 — Persona, not schema dump:**
```
Think like a seasoned data analyst: curious, methodical, hypothesis-driven.
Always assume the user's question is complex.
```

**Rule 2 — Safe exploration protocol (highest ROI instruction):**
```
For any unfamiliar table, first run: EVALUATE TOPN(3, tablename)
to confirm column names before writing aggregations.
```

**Rule 3 — Schema reference — table names only:**
```
# Data #
workspaceid: <uuid>
datasetid: <uuid>
tables: dim_customers, dim_products, fact_orders, ...
```
Column definitions belong in a `_metadata` table fetched at session start, NOT in the system prompt.

---

## Smart Refresh — CGO Implementation

**Problem:** Calling RefreshDataset on every DAX query wastes 4-8 seconds per turn.

**Solution:** Conversation variable guard in the topic YAML.

In `ConversationStart` topic:
```yaml
actions:
  - kind: SetVariable
    variable: Global.RefreshDone
    value: false
  - kind: SetVariable
    variable: Global.LastRefreshTime
    value: ""
```

In `SendDAXQuery` topic, wrap the refresh call:
```yaml
actions:
  - kind: ConditionGroup
    conditions:
      - condition: =Global.RefreshDone = false
        actions:
          - kind: InvokeFlowAction
            flowId: <refresh-flow-id>
            output:
              binding:
                result: Topic.RefreshResult
          - kind: SetVariable
            variable: Global.RefreshDone
            value: true
          - kind: SetVariable
            variable: Global.LastRefreshTime
            value: =Now()
  # Proceed to DAX query regardless
  - kind: InvokeFlowAction
    flowId: <dax-flow-id>
    ...
```

This ensures refresh runs once per conversation. For the 5-minute cross-session guard, add a condition: `=DateDiff(Global.LastRefreshTime, Now(), TimeUnit.Minutes) > 5`.

---

## Output Composition (CGO advantage)

CGO topics can compose multiple output types in a single turn:
- **Narrative text** — always
- **Chart Adaptive Cards** — separate topic triggered by LLM
- **Mermaid diagrams** — for schemas and flow diagrams
- **Follow-up questions** — append at end of every response

Instruction that enables this:
```
If a chart would help, invoke the chart rendering topic.
Always finish by offering 3 follow-up questions.
If available, offer to generate an HTML report saved to the user's OneDrive.
```

---

## PAC CLI Commands (CGO)

```powershell
$pac = "C:\Users\..\.nuget\packages\microsoft.powerapps.cli\2.8.1\tools\pac.exe"

# Authenticate
& $pac auth create --deviceCode --environment https://<org>.crm.dynamics.com

# Clone agent
& $pac copilot clone --bot <bot-id> --output-dir <dir>

# Push changes
& $pac copilot push --project-dir "<dir>\<AgentName>"

# Publish
& $pac copilot publish --bot <bot-id>
```

`pac copilot push` works on CGO (`default-2.1.0`) workspaces without crashing.

---

## _metadata Table Pattern (Production Schema Delivery)

Create a table inside your Power BI dataset:

| TableName | ColumnName | Description | BusinessRules |
|---|---|---|---|
| fact_orders | total_amount | Gross revenue incl. tax | Use subtotal for pre-tax |
| dim_customers | segment | Customer tier | VIP/Regular/At-Risk/New |

Agent fetches at session start: `EVALUATE _metadata`

Benefits:
- Zero per-table TOPN(3) discovery calls during session
- Data team owns it in Fabric — no agent republish when schema changes
- Scales to 50+ tables with no prompt bloat

---

## Sources
- Deployed reference: TableTalk with Fabric (github.com/NicoPilot-dev/TableTalkWithFabric)
- Test results: 19/19 questions, 87.4% quality, Grade A on 13-table ContosoRetail dataset
- PAC CLI 2.8.1, CDX environment, June 2026

