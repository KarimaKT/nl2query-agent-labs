---
name: "ngo-nl2query-patterns"
description: "Design patterns, YAML syntax, hard-won learnings, and evaluation methodology for NGO (CLICopilotRecognizer, cliagent-1.0.0) NL2Query agents. Covers YAML format, PAC CLI bugs, Dataverse API workarounds, direct connector tools, refresh strategy, OneDrive file delivery, skills format, CDP-based testing, and CGO vs NGO comparison."
---

# NGO NL2Query Patterns — Comprehensive Reference

A living reference for building, deploying, and debugging NL2Query agents using the **NGO (New Generative Orchestration)** architecture in Copilot Studio.

---

## 1. What is NGO?

NGO (New Generative Orchestration) is the next-generation agent architecture in Copilot Studio, replacing the topic/flow-based CGO model with a pure reasoning loop.

### Core components
- **Recognizer**: `CLICopilotRecognizer` — no intent classification, no topic matching
- **Schema**: `cliagent-1.0.0`
- **No topics** — agent behavior is defined entirely by instructions, Tools, and Skills
- **Reasoning loop**: Plan → Tool call → Observe → Synthesize → Repeat until complete

### Availability (as of mid-2026)
- Requires **Copilot Studio Early Release channel** (preview environment)
- Models: **Anthropic Claude series** (Opus, Sonnet, Haiku) — requires Anthropic license in the tenant
- Not yet GA; `cliagent-1.0.0` workspaces have known PAC CLI limitations (see Section 3)

### Key contrast with CGO

| Aspect | CGO | NGO |
|--------|-----|-----|
| Recognizer | `GenerativeAIRecognizer` | `CLICopilotRecognizer` |
| Configuration | Topics + flows + settings.mcs.yml | settings.mcs.yml only (Tools + Skills) |
| Reasoning | Hidden | Visible as intermediate steps in chat |
| Tool failures | PA flows common | Direct connectors preferred |

---

## 2. YAML Format (`settings.mcs.yml`)

### Minimal working settings.mcs.yml

```yaml
$schema: https://schemas.microsoft.com/copilotstudio/agent-settings/1.0
recognizer:
  $kind: CLICopilotRecognizer
schema: cliagent-1.0.0
agentSettings:
  model:
    $kind: ModelConfig
    series: Opus48
  instructions:
    segments:
      - value: >-
          You are a Power BI NL2Query assistant.
          WorkspaceID: <your-workspace-id>
          DatasetID: <your-dataset-id>
          Tables: Sales, Products, Customers, Calendar
          Before aggregating an unfamiliar table, run EVALUATE TOPN(3, tablename).
          For cross-table joins use SUMX(FILTER()) pattern.
          If a DAX query returns an error or implausible result, reformulate and retry.
          Never output raw code blocks in chat. Synthesize findings with specific numbers.
          End every analysis with 3 suggested follow-up questions.
```

### Critical rules for instructions
1. **Plain ASCII only** — no escaped underscores (`\_`), no Unicode zero-width chars (U+200B, U+200C)
2. Use `>-` (block scalar, strip) for multi-line instructions — avoids literal `\n` issues
3. Keep segments as a single-element array; multi-segment has known parsing quirks
4. **Do NOT use `pac copilot push` for settings changes** — see Section 3

### Model series values (confirmed working)
| Series value | Model |
|---|---|
| `Opus48` | Claude Opus 4 (latest) |
| `Sonnet45` | Claude Sonnet 4.5 |
| `Haiku45` | Claude Haiku 4.5 |

---

## 3. PAC CLI Bugs and Workarounds

| Bug | Symptom | Workaround |
|-----|---------|-----------|
| `pac copilot push` crash | `System.ArgumentOutOfRangeException` on cliagent-1.0.0 workspaces when modifying `settings.mcs.yml` | Use **Dataverse API PATCH** on `botId` (see Section 4) |
| `pac copilot pull` collapses YAML | Settings pulled as a single long line with literal `\n` | Never use pull output as editing base — always write `settings.mcs.yml` fresh from template |
| `pac copilot push` wipes tools | Tools added via UI (connector tools) get overwritten on next push | **NEVER run `pac push` if agent has manually-added connector tools.** Use Dataverse API PATCH for config only |
| Skills not visible in PAC CLI | No `pac copilot list-skills` command exists | Skills must be added/viewed via UI or CDP browser automation only |
| `/agents/designer/<botId>` URL 404s | "Page not found" even for valid agent IDs | Use `/agents/<botId>` — the `/designer/` variant is a dead URL in the new Copilot Studio UI |

### Safe PAC CLI operations (still OK to use)
- `pac auth create` — authenticate to environment
- `pac copilot list` — list agents (read-only)
- `pac solution pack/unpack` — solution zip operations (but don't push settings for NGO agents)

---

## 4. Dataverse API PATCH Pattern (Safe Config Update)

The **only safe way** to update NGO agent configuration without risking tool loss.

```powershell
# ── Step 1: Get Dataverse token via Az CLI ──────────────────────────────────
$dvToken = (az account get-access-token --resource "https://<orgName>.crm.dynamics.com" | ConvertFrom-Json).accessToken
$orgUrl   = "https://<orgName>.api.crm.dynamics.com"
$botId    = "<your-bot-guid>"
$headers  = @{ Authorization = "Bearer $dvToken"; "Content-Type" = "application/json" }

# ── Step 2: Query current bot configuration ──────────────────────────────────
$getUrl  = "$orgUrl/api/data/v9.2/bots?`$filter=botid eq '$botId'&`$select=botid,configuration"
$botData = (Invoke-RestMethod -Uri $getUrl -Headers $headers).value[0]
$config  = $botData.configuration | ConvertFrom-Json

# ── Step 3: Set CLICopilotRecognizer ────────────────────────────────────────
$config.recognizer = [PSCustomObject]@{ '$kind' = 'CLICopilotRecognizer' }

# ── Step 4: Set model ────────────────────────────────────────────────────────
$config.agentSettings.model = [PSCustomObject]@{
    '$kind' = 'ModelConfig'
    series  = 'Opus48'
}

# ── Step 5: Set instructions ─────────────────────────────────────────────────
# CRITICAL: plain ASCII only — no \_ escapes, no zero-width chars
$instructions = @"
You are a Power BI NL2Query assistant.
WorkspaceID: $workspaceId
DatasetID: $datasetId
Tables: Sales, Products, Customers, Calendar
Before aggregating an unfamiliar table, run EVALUATE TOPN(3, tablename).
For cross-table joins use SUMX(FILTER()) pattern.
If a DAX query returns an error or implausible result, reformulate and retry.
Do NOT call RefreshDataset. Data is maintained on an external schedule.
Never output raw code blocks in chat. Synthesize findings with specific numbers.
After multi-metric analysis, offer file delivery: Option A - HTML report to OneDrive. Option B - PPTX outline.
End every analysis with 3 suggested follow-up questions.
"@

$config.agentSettings.instructions.segments[0].value = $instructions

# ── Step 6: PATCH back ───────────────────────────────────────────────────────
$patchUrl  = "$orgUrl/api/data/v9.2/bots($botId)"
$patchBody = @{ configuration = ($config | ConvertTo-Json -Depth 20 -Compress) } | ConvertTo-Json
$patchHdrs = $headers + @{ "If-Match" = "*"; "MSCRM.MergeLabels" = "true" }
Invoke-RestMethod -Method Patch -Uri $patchUrl -Headers $patchHdrs -Body $patchBody
Write-Host "Config patched successfully."
```

### Common PATCH failures
| Error | Cause | Fix |
|-------|-------|-----|
| 412 Precondition Failed | Missing `If-Match: *` header | Always include `"If-Match" = "*"` in PATCH headers |
| 401 Unauthorized | Token for wrong resource | Use the org's crm.dynamics.com URL, not management.azure.com |
| Config silently ignored | Unicode chars in instructions | Strip all non-ASCII before patching |
| 400 Bad Request | configuration field not a string | `ConvertTo-Json -Compress` then wrap in outer JSON |

---

## 5. Direct Connector Tools (Not PA Flows)

PA flows as tools hit **HTTP 500** in managed tenants and CDX environments. Use direct connector actions instead.

### Adding tools via Copilot Studio UI
Navigate to: `Agents → <agent> → Tools → "+" → Connectors`

### Recommended tools for Power BI NL2Query

| Tool | Connector | Notes |
|------|-----------|-------|
| Run a query against a dataset | Power BI | Primary DAX execution tool |
| Run a json query against a dataset | Power BI | Use for structured JSON queries |
| Refresh a dataset | Power BI | Add but **disable via instructions** in managed envs |
| Create file | OneDrive for Business | File delivery — HTML reports, PPTX outlines |

### Verify tools via Dataverse API
```powershell
$compUrl   = "$orgUrl/api/data/v9.2/botcomponents"
$compUrl  += "?`$filter=_parentbotid_value eq '$botId'&`$select=name,componenttype,content"
$components = (Invoke-RestMethod -Uri $compUrl -Headers $headers).value
$components | Select-Object name, componenttype | Format-Table -AutoSize
```
Component type `6` = Tool definition. Verify all expected tools appear before testing.

### Connection references
After adding connector tools, connection references (connrefs) must be established:
1. First use of a connector prompts "Sign in" in the Copilot Studio UI
2. Record connref GUIDs in `LEARNINGS.md` (Section 11) — reuse across agent deployments
3. Connrefs persist per-environment, not per-agent

---

## 6. CDP Browser Automation (Adding Tools and Skills)

Skills and the "create connection" step for tools **cannot be automated via PAC CLI** — they require UI interaction.

### CDP setup

```powershell
# Launch Edge with remote debugging — use a dedicated profile folder
$profilePath = "$env:LOCALAPPDATA\CopilotStudioCDP\<profileName>"
Start-Process "msedge.exe" -ArgumentList @(
    "--remote-debugging-port=9333",
    "--user-data-dir=$profilePath",
    "--no-first-run"
)
```

**IMPORTANT**: Use a unique profile folder per environment. **Never use the user's main Edge profile** (`Default`) — it will corrupt their browsing session.

### Navigation pattern

```
# Preview env
https://copilotstudio.preview.microsoft.com/environments/<envId>/agents/<botId>

# Production env
https://copilotstudio.microsoft.com/environments/<envId>/agents/<botId>
```

### React form fields — CRITICAL
Native DOM property setters (`element.value = 'x'`) do **not** trigger React state updates. Use:

```javascript
// Works for all Copilot Studio text inputs
function reactSet(element, value) {
    element.focus();
    document.execCommand('insertText', false, value);
}
```

For clearing before setting:
```javascript
element.focus();
document.execCommand('selectAll', false, null);
document.execCommand('insertText', false, value);
```

### Polling for completion

```javascript
// Poll until page content stabilizes (2 consecutive same-length reads)
let prev = 0, stable = 0;
const interval = setInterval(() => {
    const len = document.body.innerText.length;
    if (len === prev) { stable++; if (stable >= 2) { clearInterval(interval); resolve(); } }
    else { prev = len; stable = 0; }
}, 10000);
```

### Adding a Skill via CDP automation
1. Navigate to agent → Skills tab
2. Click "+" → "Add skill"
3. Enter skill name (use `reactSet`)
4. Paste skill content
5. Click "Save" — wait for confirmation toast
6. Verify skill appears in skill list

---

## 7. Instructions Design for NL2Query Agents

### Structural template

```
You are a [domain] data analyst powered by Power BI.

## Identity and Scope
[What the agent does and does not do]

## Data Context
WorkspaceID: <guid>
DatasetID: <guid>
Tables: [comma-separated list]
Note: Do NOT list column names — discover them at runtime via TOPN.

## Query Protocol
1. TOPN exploration: Before aggregating an unfamiliar table, run:
   EVALUATE TOPN(3, tablename)
2. Cross-table joins: Use SUMX(FILTER()) — push datasets have no active relationships.
3. Self-correction: If a DAX query returns an error or implausible result, reformulate and retry up to 3 times.
4. Date filtering: Use CALENDAR or Date table — never filter on string date columns.

## Operational Rules
- Do NOT call RefreshDataset. Data is on an external schedule.
- Never output raw DAX code blocks in the chat response.
- Synthesize findings with specific numbers, percentages, and trends.
- If unsure of column name, run TOPN(3) to discover — do not guess.

## Output Format
- Lead with the direct answer.
- Follow with supporting metrics.
- End with 3 suggested follow-up questions.
- For multi-metric analyses: offer file delivery.
  Option A: Save interactive HTML report to OneDrive.
  Option B: Save PPTX outline to OneDrive.
```


### Generic-first design principle

The Fabric Analyst agent is designed to be **use-case agnostic at the instruction level**. This is intentional:

- **Instructions** contain: tool routing, DAX rules, output format, adaptive TOPN logic — nothing specific to ContosoRetail
- **Skills** contain: schema (table names, column types, join keys), domain context, DAX patterns for known question types
- **Benefit:** The same agent definition deploys against any Power BI dataset — swap the skills for a different schema/domain without touching instructions or agent config

This is different from the CGO approach where dataset IDs, table names, and sometimes column hints appear directly in the agent's system prompt. Putting them in skills keeps the instruction layer clean and lets subject-matter experts update domain knowledge (a skill) without touching agent configuration.

**What belongs where:**

| Content | Instructions | Skill |
|---|---|---|
| Tool routing (which tool for what) | ✅ | |
| Dataset IDs (workspaceId, datasetId) | ✅ (just IDs) | |
| DAX rules (TOPN, SUMX/FILTER, self-correct) | ✅ | |
| Output format rules | ✅ | |
| Table names | ✅ (list only) | ✅ (with column detail) |
| Column names, types, sample values | | ✅ |
| Business rules ("no active relationships") | ✅ (structural) | ✅ (domain-specific) |
| Business conclusions ("Email ROI declining") | ❌ never | ❌ never in agent-facing skills |
| Known DAX patterns for domain questions | | ✅ |
| Pre-validated answers for testing | | ✅ (test/comparison skills only) |

### Proven DAX patterns to reference in instructions

| Pattern | Use case |
|---------|----------|
| `EVALUATE TOPN(3, 'TableName')` | Schema discovery, column validation |
| `EVALUATE SUMMARIZECOLUMNS('Dim'[Col], "Metric", [Measure])` | Standard aggregation |
| `EVALUATE SUMX(FILTER('Fact', ...), 'Fact'[Amount])` | Cross-table aggregation, push datasets |
| `VAR _base = [Measure] RETURN DIVIDE(_base, [Total])` | Ratio/percentage calculation |
| `EVALUATE ROW("Result", CALCULATE([Measure], 'Date'[Year]=2025))` | Single-cell time-filtered result |



### File delivery in NGO

NGO agents run in a container with **bash and Python available OOB**. The default delivery path requires no connector tools.

**Default path — container generates file → download link in chat**
```
Agent generates file in container (bash/python)
  → HTML report with Chart.js
  → CSV / JSON / Markdown
  → PPTX via python-pptx
Delivered as a download link directly in the chat UI
```

Instructions to use:
```
When the user asks for a report or file:
Generate it in your container using bash or python.
Deliver it as a download link in the chat.
For visual reports use HTML with Chart.js charts.
For tabular data use CSV.
Never output raw HTML or code blocks inline in chat.
```

**Optional path — OneDrive connector tool → file saved to OneDrive**

If you want files saved to the user's OneDrive instead of (or in addition to) a download link:
1. Add the **OneDrive for Business "Create file"** connector tool (Tools "+" → Connectors → OneDrive for Business)
2. Tell the agent the target path in instructions: *"If a OneDrive tool is available, save to /Documents/Reports/<filename> and return the path."*
3. User must authorize the OneDrive connector on first use (consent flow in the chat)

The OneDrive tool takes a `path` and `content` parameter. For text-based files (HTML, CSV, JSON, Markdown) pass the content string directly. For binary formats (true .pptx), use the container to generate the file and deliver as a download link instead — OneDrive "Create file" accepts text content, not binary.

### Adaptive TOPN — column-aware row budget estimation

**The problem:** The Power BI REST API can return up to 100K rows. Copilot Studio context windows are finite. A 15-column table with text fields can produce 400+ chars per row — 100 rows already blows the budget. A 3-column projection of the same table could safely fit 500. Hardcoding TOPN(50) is too conservative for narrow queries; omitting TOPN entirely risks truncation or context exhaustion for wide ones.

**The solution:** Estimate N from the schema probe, adjusted for the *specific columns your query selects* — not all columns.

```
Step 1 — Schema probe (always run first on unfamiliar tables)
  EVALUATE TOPN(3, tablename)
  Observe: column names, data types, sample value widths

Step 2 — Identify projected columns
  Note which columns your actual query will SELECT or project.
  If fetching all columns, use all. If projecting a subset, use only those.

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
  target_chars = 100000   (default; increase for larger model contexts)
  N = floor(target_chars / estimated_row_width)
  Clamp N to [50, 500]

  Examples:
    3 cols × 20 chars avg  →  row = 60   →  N = 500  → clamped to 200
    8 cols × 40 chars avg  →  row = 320  →  N = 93
    5 text cols × 80 chars →  row = 400  →  N = 75
    15 cols × 25 chars avg →  row = 375  →  N = 80

Step 6 — Apply
  EVALUATE TOPN(N, SUMMARIZECOLUMNS(col1, col2, ...), sort_col, ASC)
  or for raw row fetch:
  EVALUATE TOPN(N, tablename, sort_col, ASC)
```

**Adjusting target_chars by model context size:**

| Model | target_chars suggestion |
|---|---|
| Unknown / default | 30,000 |
| Claude Opus 4.x (200K context) | 50,000–80,000 |
| GPT-4o (128K context) | 40,000–60,000 |
| Small / limited models | 15,000–20,000 |

The deploy skill defaults to 30,000. If the user specifies a model with a known context size at deploy time, update target_chars in the instructions accordingly.

**Truncation detection:** If results look incomplete — totals inconsistent, list suspiciously round, count lower than a prior `COUNTROWS` check — treat as truncated. Retry with halved N or switch to `SUMMARIZECOLUMNS` aggregation.


---

## 8. Skills (Knowledge Segments)

Skills provide pre-compiled knowledge to the agent, reducing reasoning time and token usage on known question types.

### The definitive approach: Dataverse API POST (no CDP, no PAC CLI)

Skills are stored as `botcomponent` records in Dataverse with `componenttype: 9`. Create them directly via API — no browser automation needed.

```powershell
function Add-AgentSkill {
    param($orgUrl, $botId, $agentSchemaName, $skillName, $skillDescription, $skillInstructions)

    $dvToken = az account get-access-token --resource $orgUrl --query accessToken -o tsv
    $dvHeaders = @{
        Authorization    = "Bearer $dvToken"
        "Content-Type"   = "application/json"
        "OData-MaxVersion" = "4.0"
        "OData-Version"  = "4.0"
        "Prefer"         = "return=representation"
    }

    # Build data YAML — matches the format stored in Dataverse
    $dataYaml = "kind: InlineAgentSkill`ncontent: |`n  ---`n  name: $skillName`n  description: $skillDescription`n  ---`n  <!-- bic:source=blank -->`n"
    foreach ($line in $skillInstructions -split "`n") { $dataYaml += "  $line`n" }

    $body = @{
        name        = $skillName
        description = $skillDescription
        schemaname  = "$agentSchemaName.skill.$skillName"
        componenttype = 9
        data        = $dataYaml
        "parentbotid@odata.bind" = "/bots($botId)"
    } | ConvertTo-Json -Depth 5

    $result = Invoke-RestMethod "$orgUrl/api/data/v9.2/botcomponents" -Method POST -Headers $dvHeaders -Body $body
    Write-Host "Created skill: $($result.name) (ID: $($result.botcomponentid))"
    return $result.botcomponentid
}
```

After adding all skills, publish: `& $pac copilot publish --bot $botId`

### Check for existing skills before adding (skip-if-exists)

```powershell
$dvToken = az account get-access-token --resource $orgUrl --query accessToken -o tsv
$dvHeaders = @{ Authorization = "Bearer $dvToken"; "Content-Type" = "application/json" }
$components = (Invoke-RestMethod `
    "$orgUrl/api/data/v9.2/botcomponents?`$filter=_parentbotid_value eq '$botId'&`$select=name,componenttype,schemaname" `
    -Headers $dvHeaders).value
$existingSkills = $components | Where-Object { ---
name: "ngo-nl2query-patterns"
description: "Design patterns, YAML syntax, hard-won learnings, and evaluation methodology for NGO (CLICopilotRecognizer, cliagent-1.0.0) NL2Query agents. Covers YAML format, PAC CLI bugs, Dataverse API workarounds, direct connector tools, refresh strategy, OneDrive file delivery, skills format, CDP-based testing, and CGO vs NGO comparison."
---

# NGO NL2Query Patterns — Comprehensive Reference

A living reference for building, deploying, and debugging NL2Query agents using the **NGO (New Generative Orchestration)** architecture in Copilot Studio.

---

## 1. What is NGO?

NGO (New Generative Orchestration) is the next-generation agent architecture in Copilot Studio, replacing the topic/flow-based CGO model with a pure reasoning loop.

### Core components
- **Recognizer**: `CLICopilotRecognizer` — no intent classification, no topic matching
- **Schema**: `cliagent-1.0.0`
- **No topics** — agent behavior is defined entirely by instructions, Tools, and Skills
- **Reasoning loop**: Plan → Tool call → Observe → Synthesize → Repeat until complete

### Availability (as of mid-2026)
- Requires **Copilot Studio Early Release channel** (preview environment)
- Models: **Anthropic Claude series** (Opus, Sonnet, Haiku) — requires Anthropic license in the tenant
- Not yet GA; `cliagent-1.0.0` workspaces have known PAC CLI limitations (see Section 3)

### Key contrast with CGO

| Aspect | CGO | NGO |
|--------|-----|-----|
| Recognizer | `GenerativeAIRecognizer` | `CLICopilotRecognizer` |
| Configuration | Topics + flows + settings.mcs.yml | settings.mcs.yml only (Tools + Skills) |
| Reasoning | Hidden | Visible as intermediate steps in chat |
| Tool failures | PA flows common | Direct connectors preferred |

---

## 2. YAML Format (`settings.mcs.yml`)

### Minimal working settings.mcs.yml

```yaml
$schema: https://schemas.microsoft.com/copilotstudio/agent-settings/1.0
recognizer:
  $kind: CLICopilotRecognizer
schema: cliagent-1.0.0
agentSettings:
  model:
    $kind: ModelConfig
    series: Opus48
  instructions:
    segments:
      - value: >-
          You are a Power BI NL2Query assistant.
          WorkspaceID: <your-workspace-id>
          DatasetID: <your-dataset-id>
          Tables: Sales, Products, Customers, Calendar
          Before aggregating an unfamiliar table, run EVALUATE TOPN(3, tablename).
          For cross-table joins use SUMX(FILTER()) pattern.
          If a DAX query returns an error or implausible result, reformulate and retry.
          Never output raw code blocks in chat. Synthesize findings with specific numbers.
          End every analysis with 3 suggested follow-up questions.
```

### Critical rules for instructions
1. **Plain ASCII only** — no escaped underscores (`\_`), no Unicode zero-width chars (U+200B, U+200C)
2. Use `>-` (block scalar, strip) for multi-line instructions — avoids literal `\n` issues
3. Keep segments as a single-element array; multi-segment has known parsing quirks
4. **Do NOT use `pac copilot push` for settings changes** — see Section 3

### Model series values (confirmed working)
| Series value | Model |
|---|---|
| `Opus48` | Claude Opus 4 (latest) |
| `Sonnet45` | Claude Sonnet 4.5 |
| `Haiku45` | Claude Haiku 4.5 |

---

## 3. PAC CLI Bugs and Workarounds

| Bug | Symptom | Workaround |
|-----|---------|-----------|
| `pac copilot push` crash | `System.ArgumentOutOfRangeException` on cliagent-1.0.0 workspaces when modifying `settings.mcs.yml` | Use **Dataverse API PATCH** on `botId` (see Section 4) |
| `pac copilot pull` collapses YAML | Settings pulled as a single long line with literal `\n` | Never use pull output as editing base — always write `settings.mcs.yml` fresh from template |
| `pac copilot push` wipes tools | Tools added via UI (connector tools) get overwritten on next push | **NEVER run `pac push` if agent has manually-added connector tools.** Use Dataverse API PATCH for config only |
| Skills not visible in PAC CLI | No `pac copilot list-skills` command exists | Skills must be added/viewed via UI or CDP browser automation only |
| `/agents/designer/<botId>` URL 404s | "Page not found" even for valid agent IDs | Use `/agents/<botId>` — the `/designer/` variant is a dead URL in the new Copilot Studio UI |

### Safe PAC CLI operations (still OK to use)
- `pac auth create` — authenticate to environment
- `pac copilot list` — list agents (read-only)
- `pac solution pack/unpack` — solution zip operations (but don't push settings for NGO agents)

---

## 4. Dataverse API PATCH Pattern (Safe Config Update)

The **only safe way** to update NGO agent configuration without risking tool loss.

```powershell
# ── Step 1: Get Dataverse token via Az CLI ──────────────────────────────────
$dvToken = (az account get-access-token --resource "https://<orgName>.crm.dynamics.com" | ConvertFrom-Json).accessToken
$orgUrl   = "https://<orgName>.api.crm.dynamics.com"
$botId    = "<your-bot-guid>"
$headers  = @{ Authorization = "Bearer $dvToken"; "Content-Type" = "application/json" }

# ── Step 2: Query current bot configuration ──────────────────────────────────
$getUrl  = "$orgUrl/api/data/v9.2/bots?`$filter=botid eq '$botId'&`$select=botid,configuration"
$botData = (Invoke-RestMethod -Uri $getUrl -Headers $headers).value[0]
$config  = $botData.configuration | ConvertFrom-Json

# ── Step 3: Set CLICopilotRecognizer ────────────────────────────────────────
$config.recognizer = [PSCustomObject]@{ '$kind' = 'CLICopilotRecognizer' }

# ── Step 4: Set model ────────────────────────────────────────────────────────
$config.agentSettings.model = [PSCustomObject]@{
    '$kind' = 'ModelConfig'
    series  = 'Opus48'
}

# ── Step 5: Set instructions ─────────────────────────────────────────────────
# CRITICAL: plain ASCII only — no \_ escapes, no zero-width chars
$instructions = @"
You are a Power BI NL2Query assistant.
WorkspaceID: $workspaceId
DatasetID: $datasetId
Tables: Sales, Products, Customers, Calendar
Before aggregating an unfamiliar table, run EVALUATE TOPN(3, tablename).
For cross-table joins use SUMX(FILTER()) pattern.
If a DAX query returns an error or implausible result, reformulate and retry.
Do NOT call RefreshDataset. Data is maintained on an external schedule.
Never output raw code blocks in chat. Synthesize findings with specific numbers.
After multi-metric analysis, offer file delivery: Option A - HTML report to OneDrive. Option B - PPTX outline.
End every analysis with 3 suggested follow-up questions.
"@

$config.agentSettings.instructions.segments[0].value = $instructions

# ── Step 6: PATCH back ───────────────────────────────────────────────────────
$patchUrl  = "$orgUrl/api/data/v9.2/bots($botId)"
$patchBody = @{ configuration = ($config | ConvertTo-Json -Depth 20 -Compress) } | ConvertTo-Json
$patchHdrs = $headers + @{ "If-Match" = "*"; "MSCRM.MergeLabels" = "true" }
Invoke-RestMethod -Method Patch -Uri $patchUrl -Headers $patchHdrs -Body $patchBody
Write-Host "Config patched successfully."
```

### Common PATCH failures
| Error | Cause | Fix |
|-------|-------|-----|
| 412 Precondition Failed | Missing `If-Match: *` header | Always include `"If-Match" = "*"` in PATCH headers |
| 401 Unauthorized | Token for wrong resource | Use the org's crm.dynamics.com URL, not management.azure.com |
| Config silently ignored | Unicode chars in instructions | Strip all non-ASCII before patching |
| 400 Bad Request | configuration field not a string | `ConvertTo-Json -Compress` then wrap in outer JSON |

---

## 5. Direct Connector Tools (Not PA Flows)

PA flows as tools hit **HTTP 500** in managed tenants and CDX environments. Use direct connector actions instead.

### Adding tools via Copilot Studio UI
Navigate to: `Agents → <agent> → Tools → "+" → Connectors`

### Recommended tools for Power BI NL2Query

| Tool | Connector | Notes |
|------|-----------|-------|
| Run a query against a dataset | Power BI | Primary DAX execution tool |
| Run a json query against a dataset | Power BI | Use for structured JSON queries |
| Refresh a dataset | Power BI | Add but **disable via instructions** in managed envs |
| Create file | OneDrive for Business | File delivery — HTML reports, PPTX outlines |

### Verify tools via Dataverse API
```powershell
$compUrl   = "$orgUrl/api/data/v9.2/botcomponents"
$compUrl  += "?`$filter=_parentbotid_value eq '$botId'&`$select=name,componenttype,content"
$components = (Invoke-RestMethod -Uri $compUrl -Headers $headers).value
$components | Select-Object name, componenttype | Format-Table -AutoSize
```
Component type `6` = Tool definition. Verify all expected tools appear before testing.

### Connection references
After adding connector tools, connection references (connrefs) must be established:
1. First use of a connector prompts "Sign in" in the Copilot Studio UI
2. Record connref GUIDs in `LEARNINGS.md` (Section 11) — reuse across agent deployments
3. Connrefs persist per-environment, not per-agent

---

## 6. CDP Browser Automation (Adding Tools and Skills)

Skills and the "create connection" step for tools **cannot be automated via PAC CLI** — they require UI interaction.

### CDP setup

```powershell
# Launch Edge with remote debugging — use a dedicated profile folder
$profilePath = "$env:LOCALAPPDATA\CopilotStudioCDP\<profileName>"
Start-Process "msedge.exe" -ArgumentList @(
    "--remote-debugging-port=9333",
    "--user-data-dir=$profilePath",
    "--no-first-run"
)
```

**IMPORTANT**: Use a unique profile folder per environment. **Never use the user's main Edge profile** (`Default`) — it will corrupt their browsing session.

### Navigation pattern

```
# Preview env
https://copilotstudio.preview.microsoft.com/environments/<envId>/agents/<botId>

# Production env
https://copilotstudio.microsoft.com/environments/<envId>/agents/<botId>
```

### React form fields — CRITICAL
Native DOM property setters (`element.value = 'x'`) do **not** trigger React state updates. Use:

```javascript
// Works for all Copilot Studio text inputs
function reactSet(element, value) {
    element.focus();
    document.execCommand('insertText', false, value);
}
```

For clearing before setting:
```javascript
element.focus();
document.execCommand('selectAll', false, null);
document.execCommand('insertText', false, value);
```

### Polling for completion

```javascript
// Poll until page content stabilizes (2 consecutive same-length reads)
let prev = 0, stable = 0;
const interval = setInterval(() => {
    const len = document.body.innerText.length;
    if (len === prev) { stable++; if (stable >= 2) { clearInterval(interval); resolve(); } }
    else { prev = len; stable = 0; }
}, 10000);
```

### Adding a Skill via CDP automation
1. Navigate to agent → Skills tab
2. Click "+" → "Add skill"
3. Enter skill name (use `reactSet`)
4. Paste skill content
5. Click "Save" — wait for confirmation toast
6. Verify skill appears in skill list

---

## 7. Instructions Design for NL2Query Agents

### Structural template

```
You are a [domain] data analyst powered by Power BI.

## Identity and Scope
[What the agent does and does not do]

## Data Context
WorkspaceID: <guid>
DatasetID: <guid>
Tables: [comma-separated list]
Note: Do NOT list column names — discover them at runtime via TOPN.

## Query Protocol
1. TOPN exploration: Before aggregating an unfamiliar table, run:
   EVALUATE TOPN(3, tablename)
2. Cross-table joins: Use SUMX(FILTER()) — push datasets have no active relationships.
3. Self-correction: If a DAX query returns an error or implausible result, reformulate and retry up to 3 times.
4. Date filtering: Use CALENDAR or Date table — never filter on string date columns.

## Operational Rules
- Do NOT call RefreshDataset. Data is on an external schedule.
- Never output raw DAX code blocks in the chat response.
- Synthesize findings with specific numbers, percentages, and trends.
- If unsure of column name, run TOPN(3) to discover — do not guess.

## Output Format
- Lead with the direct answer.
- Follow with supporting metrics.
- End with 3 suggested follow-up questions.
- For multi-metric analyses: offer file delivery.
  Option A: Save interactive HTML report to OneDrive.
  Option B: Save PPTX outline to OneDrive.
```


### Generic-first design principle

The Fabric Analyst agent is designed to be **use-case agnostic at the instruction level**. This is intentional:

- **Instructions** contain: tool routing, DAX rules, output format, adaptive TOPN logic — nothing specific to ContosoRetail
- **Skills** contain: schema (table names, column types, join keys), domain context, DAX patterns for known question types
- **Benefit:** The same agent definition deploys against any Power BI dataset — swap the skills for a different schema/domain without touching instructions or agent config

This is different from the CGO approach where dataset IDs, table names, and sometimes column hints appear directly in the agent's system prompt. Putting them in skills keeps the instruction layer clean and lets subject-matter experts update domain knowledge (a skill) without touching agent configuration.

**What belongs where:**

| Content | Instructions | Skill |
|---|---|---|
| Tool routing (which tool for what) | ✅ | |
| Dataset IDs (workspaceId, datasetId) | ✅ (just IDs) | |
| DAX rules (TOPN, SUMX/FILTER, self-correct) | ✅ | |
| Output format rules | ✅ | |
| Table names | ✅ (list only) | ✅ (with column detail) |
| Column names, types, sample values | | ✅ |
| Business rules ("no active relationships") | ✅ (structural) | ✅ (domain-specific) |
| Business conclusions ("Email ROI declining") | ❌ never | ❌ never in agent-facing skills |
| Known DAX patterns for domain questions | | ✅ |
| Pre-validated answers for testing | | ✅ (test/comparison skills only) |

### Proven DAX patterns to reference in instructions

| Pattern | Use case |
|---------|----------|
| `EVALUATE TOPN(3, 'TableName')` | Schema discovery, column validation |
| `EVALUATE SUMMARIZECOLUMNS('Dim'[Col], "Metric", [Measure])` | Standard aggregation |
| `EVALUATE SUMX(FILTER('Fact', ...), 'Fact'[Amount])` | Cross-table aggregation, push datasets |
| `VAR _base = [Measure] RETURN DIVIDE(_base, [Total])` | Ratio/percentage calculation |
| `EVALUATE ROW("Result", CALCULATE([Measure], 'Date'[Year]=2025))` | Single-cell time-filtered result |


### File delivery in NGO — two paths

NGO agents run in a container that has **bash and Python available OOB**. This means file generation does not require a connector tool — the agent generates the file in its container and delivers it as a **download link in the chat UI**.

**Path 1 — Container → download link (default, no tools needed)**
- Agent generates file content using container tools (bash, python, python-pptx, etc.)
- File is delivered as a download link directly in the chat
- Works for: HTML reports, CSV, JSON, PPTX (via python-pptx), Markdown
- Use this path by default

**Path 2 — OneDrive connector tool → saved to OneDrive**
- Requires the "Create file" OneDrive for Business connector tool
- Agent passes filename + content → file lands in user's OneDrive → agent returns the path
- Good when users want persistent storage or need to share files
- User must have authorized the OneDrive connector (consent flow on first use)

**What the previous test showed:** The agent was finding the right writeable path in its container for Path 1, but hit a directory permissions issue mid-run. It successfully retrieved 500 rows / 111 KB — the container capability is real. Path 1 just needs the agent to know the correct writeable directory.

**Instructions guidance:**
- Tell the agent to use container tools to generate files and deliver as download links
- Offer OneDrive as an optional second path if the tool is connected
- Do NOT tell the agent to "pass HTML as a string to the Create file tool" — that bypasses the container's native generation capability

### Adaptive TOPN — column-aware row budget estimation

**The problem:** The Power BI REST API can return up to 100K rows. Copilot Studio context windows are finite. A 15-column table with text fields can produce 400+ chars per row — 100 rows already blows the budget. A 3-column projection of the same table could safely fit 500. Hardcoding TOPN(50) is too conservative for narrow queries; omitting TOPN entirely risks truncation or context exhaustion for wide ones.

**The solution:** Estimate N from the schema probe, adjusted for the *specific columns your query selects* — not all columns.

```
Step 1 — Schema probe (always run first on unfamiliar tables)
  EVALUATE TOPN(3, tablename)
  Observe: column names, data types, sample value widths

Step 2 — Identify projected columns
  Note which columns your actual query will SELECT or project.
  If fetching all columns, use all. If projecting a subset, use only those.

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
  target_chars = 100000   (default; increase for larger model contexts)
  N = floor(target_chars / estimated_row_width)
  Clamp N to [50, 500]

  Examples:
    3 cols × 20 chars avg  →  row = 60   →  N = 500  → clamped to 200
    8 cols × 40 chars avg  →  row = 320  →  N = 93
    5 text cols × 80 chars →  row = 400  →  N = 75
    15 cols × 25 chars avg →  row = 375  →  N = 80

Step 6 — Apply
  EVALUATE TOPN(N, SUMMARIZECOLUMNS(col1, col2, ...), sort_col, ASC)
  or for raw row fetch:
  EVALUATE TOPN(N, tablename, sort_col, ASC)
```

**Adjusting target_chars by model context size:**

| Model | target_chars suggestion |
|---|---|
| Unknown / default | 30,000 |
| Claude Opus 4.x (200K context) | 50,000–80,000 |
| GPT-4o (128K context) | 40,000–60,000 |
| Small / limited models | 15,000–20,000 |

The deploy skill defaults to 30,000. If the user specifies a model with a known context size at deploy time, update target_chars in the instructions accordingly.

**Truncation detection:** If results look incomplete — totals inconsistent, list suspiciously round, count lower than a prior `COUNTROWS` check — treat as truncated. Retry with halved N or switch to `SUMMARIZECOLUMNS` aggregation.


---

## 8. Skills (Knowledge Segments)

Skills provide pre-compiled knowledge to the agent, reducing reasoning time and token usage.

### Recommended skill set for Power BI NL2Query

| Skill name | Content | Purpose |
|-----------|---------|---------|
| `schema-definitions` | Table names, column names, data types, business rules, join keys | Eliminates TOPN exploration for known tables |
| `dax-patterns-<domain>` | Known DAX patterns for domain (e.g., `dax-patterns-manufacturing`) | Copy-paste DAX for common question types |
| `dax-patterns-financials` | Revenue, cost, margin, ROI, variance patterns | Finance-specific query templates |

### Schema skill template

```markdown
# Schema: <DatasetName>

## Tables

### Sales
- SalesID (int, PK)
- ProductKey (int, FK → Products[ProductKey])
- CustomerKey (int, FK → Customers[CustomerKey])
- DateKey (int, FK → Calendar[DateKey])
- Revenue (decimal)
- Quantity (int)
- Region (text: "North", "South", "East", "West")

### Products
- ProductKey (int, PK)
- ProductName (text)
- Category (text)
- UnitCost (decimal)

## Business Rules
- Revenue = Quantity * UnitPrice (not stored; calculated)
- Gross Margin = Revenue - (Quantity * UnitCost)
- No active relationships — use SUMX(FILTER()) for cross-table joins

## Common Join Patterns
- Sales ↔ Products: FILTER('Products', 'Products'[ProductKey] = EARLIER('Sales'[ProductKey]))
- Sales ↔ Calendar: FILTER('Calendar', 'Calendar'[DateKey] = EARLIER('Sales'[DateKey]))
```

### Skills are NOT visible in PAC CLI
- No `pac copilot list-skills` or `pac copilot add-skill` commands exist
- Must be added via Copilot Studio UI or CDP automation (Section 6)
- Skills content is stored as `botcomponent` records in Dataverse (componenttype `8`)

---

## 9. CDX Agenticruntime Outage Pattern

### Symptom
All agents show: `BotDefinitionOverride contains invalid YAML` — even agents that were working minutes before and have not been modified.

### Diagnosis
This is a **platform outage**, not a YAML authoring error.

1. Check a **known-working agent** in the same environment
2. If it also fails with the same error → platform outage
3. If only your agent fails → check your YAML (Section 2)

### Recovery
- CDX agenticruntime outages typically recover in **1–4 hours**
- No action required on the agent configuration
- Check Copilot Studio service health dashboard for status
- Do NOT attempt YAML fixes during a platform outage — you will overwrite known-good config

### False positive triggers
- Deploying during a rolling restart of agenticruntime pods
- Token expiry mid-session
- Quota throttling in CDX environments (shared, limited capacity)

---

## 10. CGO vs NGO Comparison

| Dimension | CGO | NGO |
|-----------|-----|-----|
| Orchestrator | `GenerativeAIRecognizer` | `CLICopilotRecognizer` |
| Schema | `default-2.1.0` | `cliagent-1.0.0` |
| Configuration | topics + flows + `settings.mcs.yml` | `settings.mcs.yml` only (Tools + Skills) |
| PAC CLI push | Works for topics and settings | Crashes on settings changes — use Dataverse API |
| Tool source | PA flows or direct connectors | Direct connectors only (PA flows hit HTTP 500) |
| Inline charts | Adaptive Cards via topic action | Not supported — deliver via file (OneDrive) |
| In-product evaluation | Available | Not yet available (mid-2026) |
| Session/conversation state | Conversation variables (persistent per turn) | Limited — no persistent cross-turn variables |
| Reasoning visibility | Hidden | Visible in chat as intermediate steps |
| Deployment | Solution zip (pac copilot init/pack/push) | Solution zip for agent shell, then Dataverse API for config |
| Skills support | Not available | Available (added via UI) |
| Tool discovery | Static (defined in topics) | Dynamic (agent decides which tool to call) |
| Debug experience | Step through topics in Test tab | Reasoning chain visible; no step-through |
| PA flow tools | Fully supported | HTTP 500 in managed/CDX environments |

### When to choose NGO over CGO
- Complex multi-step reasoning (NL2Query, data analysis, multi-tool chains)
- You want to see the agent's reasoning process
- You have access to Anthropic Claude models via tenant license
- Direct connector tools are sufficient (no need for complex PA flow logic)

### When to stick with CGO
- Strict conversation flow control required
- Adaptive Cards / rich UI responses needed
- Existing topic library you want to reuse
- Environment does not have Anthropic license
- In-product evaluation pipeline is required

---

## 11. LEARNINGS.md Pattern

Every NGO agent deployment should maintain a `LEARNINGS.md` in the working directory.
This file persists discovered IDs and session notes across runs so you don't re-discover known values.

### Template

```markdown
# <AgentName> — Session Learnings
Last updated: <YYYY-MM-DD>
User: <email>
Environment: <envId>

## Discovered IDs
- envId:        <guid>
- orgUrl:       https://<orgName>.api.crm.dynamics.com
- botId:        <guid>
- workspaceId:  <guid>
- datasetId:    <guid>
- tenantId:     <guid>

## Connection IDs (connector references)
- Power BI connref:           /providers/Microsoft.PowerApps/apis/shared_powerbi/connections/<connId>
- OneDrive connref:           /providers/Microsoft.PowerApps/apis/shared_onedriveforbusiness/connections/<connId>

## Session Notes
- <YYYY-MM-DD>: <what was learned, what worked, what failed>
- <YYYY-MM-DD>: TOPN query confirmed working; SUMMARIZECOLUMNS fails on push dataset (use SUMX)
- <YYYY-MM-DD>: Refresh tool disabled in instructions — CDX quota exceeded on dataset refresh
```

### Skill startup procedure

```powershell
# At start of every skill run — load known IDs from LEARNINGS.md
$workDir  = "C:\src\Fabric\agents\<agentName>"
$learnFile = "$workDir\LEARNINGS.md"

$knownIds = @{}
if (Test-Path $learnFile) {
    $lines = Get-Content $learnFile
    foreach ($line in $lines) {
        if ($line -match "^- (\w+):\s+(.+)$") {
            $knownIds[$matches[1]] = $matches[2].Trim()
        }
    }
    Write-Host "Loaded known IDs: $($knownIds.Keys -join ', ')"
}

# Use discovered IDs if available; otherwise resolve fresh
$botId       = $knownIds['botId']       ?? (Resolve-BotId -AgentName $agentName)
$workspaceId = $knownIds['workspaceId'] ?? (Resolve-WorkspaceId -AgentName $agentName)
```

### Skill completion procedure

```powershell
# At end of skill run — update LEARNINGS.md with new IDs and session note
$sessionNote = "$(Get-Date -Format 'yyyy-MM-dd'): Deployed config. botId=$botId, model=Opus48. Instructions updated."

# Update or append IDs section
$content = Get-Content $learnFile -Raw
$content  = $content -replace "(?m)^- botId:.*$", "- botId:        $botId"
$content  = $content -replace "(?m)^- workspaceId:.*$", "- workspaceId:  $workspaceId"
$content  = $content -replace "(?m)^- datasetId:.*$", "- datasetId:    $datasetId"

# Append session note
$content += "`n- $sessionNote"
Set-Content -Path $learnFile -Value $content -Encoding UTF8

Write-Host "LEARNINGS.md updated."
```

---

## 12. Quick Reference Checklist

### New NGO agent deployment
- [ ] Create agent shell via Copilot Studio UI (or `pac copilot init`)
- [ ] Record `botId` in `LEARNINGS.md`
- [ ] Add connector tools via UI: Power BI (3 tools) + OneDrive (Create file)
- [ ] Establish connections (sign-in prompt for each connector)
- [ ] Record connref GUIDs in `LEARNINGS.md`
- [ ] Write `settings.mcs.yml` from template (Section 2) — plain ASCII only
- [ ] PATCH configuration via Dataverse API (Section 4) — NOT `pac copilot push`
- [ ] Add Skills via CDP or UI (Section 6/8)
- [ ] Test: run TOPN(3) query, run aggregation, verify file delivery
- [ ] Publish agent

### Debugging runbook
1. **Agent says "invalid YAML"** → Check if platform outage (Section 9). If not, re-read Section 2.
2. **Tool returns HTTP 500** → Replace PA flow with direct connector (Section 5).
3. **Instructions silently ignored** → Strip Unicode chars; re-PATCH via Dataverse API.
4. **`pac copilot push` crashes** → Switch to Dataverse API PATCH permanently (Section 4).
5. **Skills not appearing** → Add via UI or CDP automation (Section 6). PAC CLI cannot add skills.
6. **Wrong URL for agent** → Use `/agents/<botId>` not `/agents/designer/<botId>`.
.schemaname -like "*.skill.*" }
Write-Host "Existing skills: $($existingSkills.name -join ', ')"
```

### Recommended skill set for Power BI NL2Query

| Skill name | Content | Benefit |
|---|---|---|
| `schema-definitions` | All table names, column types, join keys, business rules | Eliminates TOPN exploration for known tables |
| `dax-patterns-<domain>` | Known DAX patterns for common question types | Faster, more consistent query generation |

### Schema skill format

```markdown
## <DatasetName> Schema

**Dataset type:** Power BI push dataset (no active relationships — use SUMX(FILTER()) for all cross-table joins)

## Tables

### TableName
col1 (type, PK/FK → OtherTable[col]), col2 (type), ...

## Business Rules
- Rule 1
- Rule 2

## Common Patterns
Pattern name:
DAX expression
```

### How skills appear in the solution (pac copilot clone)

When cloned, skills appear in the `translations/` folder:
```
translations/
  <schemaName>.skill.<skill-name>.mcs.yml
```

File format (what pac clone produces):
```yaml
mcs.metadata:
  componentName: <skill-name>
  description: <description>
kind: InlineAgentSkill
content: |
  ---
  name: <skill-name>
  description: <description>
  ---
  <!-- bic:source=blank -->
  <skill instructions>
```

**Important:** `pac copilot pack` and `pac copilot push` do NOT yet support `translations/`, `actions/`, or `workflows/`. These folders are captured by clone but cannot be round-tripped via push. Use Dataverse API for all writes.

### Skills vs instructions — when to use each

| Approach | Best for | Tradeoff |
|---|---|---|
| **Instructions** | Core identity, always-on rules, query protocols, dataset IDs | Applied every turn; length-limited; survives republish |
| **Skills** | Pre-compiled knowledge (schema details, DAX patterns) | Reduces reasoning overhead; added via Dataverse API; survives republish when added via API |
| **Tool descriptions** | Guiding which tool to call | Doesn't help with query correctness |

**Recommended pattern:**
- Instructions = identity + protocol + IDs + table names (list only, no columns)
- Schema skill = full column-level detail, join patterns, business rules
- DAX pattern skill(s) = domain-specific query templates

This keeps instructions short and puts detailed knowledge in skills where the reasoning loop can selectively retrieve it.

### Future: when pac copilot pack supports translations/

The YAML format is already defined (`kind: InlineAgentSkill` in `translations/*.skill.*.mcs.yml`). Once PAC CLI adds support for packing/pushing the `translations/` folder, skills can be version-controlled and deployed as part of a full solution import — no Dataverse API needed. Until then, Dataverse API POST is the automated path.

## 9. CDX Agenticruntime Outage Pattern

### Symptom
All agents show: `BotDefinitionOverride contains invalid YAML` — even agents that were working minutes before and have not been modified.

### Diagnosis
This is a **platform outage**, not a YAML authoring error.

1. Check a **known-working agent** in the same environment
2. If it also fails with the same error → platform outage
3. If only your agent fails → check your YAML (Section 2)

### Recovery
- CDX agenticruntime outages typically recover in **1–4 hours**
- No action required on the agent configuration
- Check Copilot Studio service health dashboard for status
- Do NOT attempt YAML fixes during a platform outage — you will overwrite known-good config

### False positive triggers
- Deploying during a rolling restart of agenticruntime pods
- Token expiry mid-session
- Quota throttling in CDX environments (shared, limited capacity)

---

## 10. CGO vs NGO Comparison

| Dimension | CGO | NGO |
|-----------|-----|-----|
| Orchestrator | `GenerativeAIRecognizer` | `CLICopilotRecognizer` |
| Schema | `default-2.1.0` | `cliagent-1.0.0` |
| Configuration | topics + flows + `settings.mcs.yml` | `settings.mcs.yml` only (Tools + Skills) |
| PAC CLI push | Works for topics and settings | Crashes on settings changes — use Dataverse API |
| Tool source | PA flows or direct connectors | Direct connectors only (PA flows hit HTTP 500) |
| Inline charts | Adaptive Cards via topic action | Not supported — deliver via file (OneDrive) |
| In-product evaluation | Available | Not yet available (mid-2026) |
| Session/conversation state | Conversation variables (persistent per turn) | Limited — no persistent cross-turn variables |
| Reasoning visibility | Hidden | Visible in chat as intermediate steps |
| Deployment | Solution zip (pac copilot init/pack/push) | Solution zip for agent shell, then Dataverse API for config |
| Skills support | Not available | Available (added via UI) |
| Tool discovery | Static (defined in topics) | Dynamic (agent decides which tool to call) |
| Debug experience | Step through topics in Test tab | Reasoning chain visible; no step-through |
| PA flow tools | Fully supported | HTTP 500 in managed/CDX environments |

### When to choose NGO over CGO
- Complex multi-step reasoning (NL2Query, data analysis, multi-tool chains)
- You want to see the agent's reasoning process
- You have access to Anthropic Claude models via tenant license
- Direct connector tools are sufficient (no need for complex PA flow logic)

### When to stick with CGO
- Strict conversation flow control required
- Adaptive Cards / rich UI responses needed
- Existing topic library you want to reuse
- Environment does not have Anthropic license
- In-product evaluation pipeline is required

---

## 11. LEARNINGS.md Pattern

Every NGO agent deployment should maintain a `LEARNINGS.md` in the working directory.
This file persists discovered IDs and session notes across runs so you don't re-discover known values.

### Template

```markdown
# <AgentName> — Session Learnings
Last updated: <YYYY-MM-DD>
User: <email>
Environment: <envId>

## Discovered IDs
- envId:        <guid>
- orgUrl:       https://<orgName>.api.crm.dynamics.com
- botId:        <guid>
- workspaceId:  <guid>
- datasetId:    <guid>
- tenantId:     <guid>

## Connection IDs (connector references)
- Power BI connref:           /providers/Microsoft.PowerApps/apis/shared_powerbi/connections/<connId>
- OneDrive connref:           /providers/Microsoft.PowerApps/apis/shared_onedriveforbusiness/connections/<connId>

## Session Notes
- <YYYY-MM-DD>: <what was learned, what worked, what failed>
- <YYYY-MM-DD>: TOPN query confirmed working; SUMMARIZECOLUMNS fails on push dataset (use SUMX)
- <YYYY-MM-DD>: Refresh tool disabled in instructions — CDX quota exceeded on dataset refresh
```

### Skill startup procedure

```powershell
# At start of every skill run — load known IDs from LEARNINGS.md
$workDir  = "C:\src\Fabric\agents\<agentName>"
$learnFile = "$workDir\LEARNINGS.md"

$knownIds = @{}
if (Test-Path $learnFile) {
    $lines = Get-Content $learnFile
    foreach ($line in $lines) {
        if ($line -match "^- (\w+):\s+(.+)$") {
            $knownIds[$matches[1]] = $matches[2].Trim()
        }
    }
    Write-Host "Loaded known IDs: $($knownIds.Keys -join ', ')"
}

# Use discovered IDs if available; otherwise resolve fresh
$botId       = $knownIds['botId']       ?? (Resolve-BotId -AgentName $agentName)
$workspaceId = $knownIds['workspaceId'] ?? (Resolve-WorkspaceId -AgentName $agentName)
```

### Skill completion procedure

```powershell
# At end of skill run — update LEARNINGS.md with new IDs and session note
$sessionNote = "$(Get-Date -Format 'yyyy-MM-dd'): Deployed config. botId=$botId, model=Opus48. Instructions updated."

# Update or append IDs section
$content = Get-Content $learnFile -Raw
$content  = $content -replace "(?m)^- botId:.*$", "- botId:        $botId"
$content  = $content -replace "(?m)^- workspaceId:.*$", "- workspaceId:  $workspaceId"
$content  = $content -replace "(?m)^- datasetId:.*$", "- datasetId:    $datasetId"

# Append session note
$content += "`n- $sessionNote"
Set-Content -Path $learnFile -Value $content -Encoding UTF8

Write-Host "LEARNINGS.md updated."
```

---

## 12. Quick Reference Checklist

### New NGO agent deployment
- [ ] Create agent shell via Copilot Studio UI (or `pac copilot init`)
- [ ] Record `botId` in `LEARNINGS.md`
- [ ] Add connector tools via UI: Power BI (3 tools) + OneDrive (Create file)
- [ ] Establish connections (sign-in prompt for each connector)
- [ ] Record connref GUIDs in `LEARNINGS.md`
- [ ] Write `settings.mcs.yml` from template (Section 2) — plain ASCII only
- [ ] PATCH configuration via Dataverse API (Section 4) — NOT `pac copilot push`
- [ ] Add Skills via CDP or UI (Section 6/8)
- [ ] Test: run TOPN(3) query, run aggregation, verify file delivery
- [ ] Publish agent

### Debugging runbook
1. **Agent says "invalid YAML"** → Check if platform outage (Section 9). If not, re-read Section 2.
2. **Tool returns HTTP 500** → Replace PA flow with direct connector (Section 5).
3. **Instructions silently ignored** → Strip Unicode chars; re-PATCH via Dataverse API.
4. **`pac copilot push` crashes** → Switch to Dataverse API PATCH permanently (Section 4).
5. **Skills not appearing** → Add via UI or CDP automation (Section 6). PAC CLI cannot add skills.
6. **Wrong URL for agent** → Use `/agents/<botId>` not `/agents/designer/<botId>`.






