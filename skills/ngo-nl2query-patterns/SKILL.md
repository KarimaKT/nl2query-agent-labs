---
name: "ngo-nl2query-patterns"
description: "Design patterns, YAML syntax, hard-won learnings, and evaluation methodology for NGO (CLICopilotRecognizer, cliagent-1.0.0) NL2Query agents. Covers YAML format, PAC CLI bugs, Dataverse API workarounds, direct connector tools, refresh strategy, file delivery, skills format, CDP-based testing, and CGO vs NGO comparison."
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
- Requires a Copilot Studio environment with the new orchestration experience
- Models: **Anthropic Claude series** (Opus, Sonnet, Haiku) — requires Anthropic license in the tenant
- Not yet GA; `cliagent-1.0.0` workspaces have known PAC CLI limitations (see Section 3)

### Key contrast with CGO

| Aspect | CGO | NGO |
|--------|-----|-----|
| Recognizer | `GenerativeAIRecognizer` | `CLICopilotRecognizer` |
| Configuration | Topics + flows + settings.mcs.yml | settings.mcs.yml only (Tools + Skills) |
| Reasoning | Hidden | Visible as intermediate steps in chat |
| Tool types | PA flows (InvokeFlowTaskAction) | Direct connectors + Workflows (new) |

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

## 5. Tools: Direct Connectors and Workflows

NGO supports two tool types:

- **Direct connector actions** — call a connector operation directly (e.g. Power BI `ExecuteDatasetQuery`). Simpler, no PA license needed.
- **Workflows** — the new PA flow experience native to NGO agents. More flexible than CGO's InvokeFlowTaskAction; supports complex logic, multi-step orchestration, and external integrations.

**Note on legacy PA flows as tools:** Classic PA flows wired as tools via `InvokeFlowTaskAction` hit HTTP 500 in some managed environments. Prefer direct connector actions or Workflows instead.

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
For visual reports generate HTML with Chart.js charts.
For presentations generate a PPT using python-pptx.
Never output raw HTML or code blocks inline in chat.

HTML report structure (use for all multi-metric analyses):
- Title with agent name, dataset name, and date
- Executive summary: 3-5 bullet key findings with specific numbers
- One section per analysis area with: narrative, Chart.js chart, data table
- Footer with data freshness note and follow-up questions

PPT structure:
- Slide 1: Title + executive summary bullets
- One slide per analysis area with chart and key numbers
- Final slide: recommendations + next steps

If a report file already exists from this conversation:
- Update it in place rather than creating a new file
- Add new sections or update existing ones with the latest data
- Keep the same filename; note what changed in the chat
```

**Optional path — SharePoint connector tool → file saved to SharePoint**

If you want files saved to the user's OneDrive instead of (or in addition to) a download link:
1. Add the **SharePoint "Create file"** connector tool (Tools "+" → Connectors → OneDrive for Business)
2. Tell the agent the target path in instructions: *"If a SharePoint tool is available, save to /sites/<YourSite>/Shared Documents/Reports/<filename> and return the path."*
3. User must authorize the SharePoint connector on first use (consent flow in the chat)

The SharePoint tool takes a `path` and `content` parameter. For text-based files (HTML, CSV, JSON, Markdown) pass the content string directly. For binary formats (true .pptx), use the container to generate the file and deliver as a download link instead — OneDrive "Create file" accepts text content, not binary.

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
description: "Design patterns, YAML syntax, hard-won learnings, and evaluation methodology for NGO (CLICopilotRecognizer, cliagent-1.0.0) NL2Query agents. Covers YAML format, PAC CLI bugs, Dataverse API workarounds, direct connector tools, refresh strategy, file delivery, skills format, CDP-based testing, and CGO vs NGO comparison."