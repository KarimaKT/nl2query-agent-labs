---
name: "copilot-studio-new-orchestrator"
description: "Comprehensive reference for building Copilot Studio agents with the New Generative Orchestrator (CLICopilotRecognizer, cliagent-1.0.0). Covers YAML format, PAC CLI bugs, Dataverse API patterns, tools (connectors + Workflows), Skills via API, instructions design, file delivery, CDP automation, and known gotchas."
---

# Copilot Studio New Generative Orchestrator — Comprehensive Reference

Accumulated from hands-on deployment of agents using the New Generative Orchestrator in Copilot Studio.
Sources: live UI exploration via CDP, pac copilot clone, Dataverse API inspection.

---

## 1. What is the New Generative Orchestrator

The New Generative Orchestrator (the default mode in the new Copilot Studio UI) is the next-generation agent
architecture, replacing the topic/flow-based Classic Generative Orchestration (CGO) model with a pure reasoning loop.

### Core components

- **Recognizer**: `CLICopilotRecognizer` — no intent classification, no topic matching
- **Schema**: `cliagent-1.0.0`
- **No topics** — behavior defined entirely by instructions, Tools, and Skills
- **Reasoning loop**: Plan -> Tool call -> Observe -> Synthesize -> Repeat until complete
- Intermediate reasoning steps are visible in chat

### Availability (as of mid-2026)

- Requires a Copilot Studio environment with the new orchestration experience enabled
- Models: **Anthropic Claude series** (Opus, Sonnet, Haiku) — requires Anthropic license in the tenant
- Not yet GA; `cliagent-1.0.0` workspaces have known PAC CLI limitations (see Section 3)

### Skills vs Knowledge

- **Skills** — structured instruction files in the "Skills" tab; provide compiled domain knowledge and behavioral rules
- **Knowledge** — document sources, SharePoint sites, web content; different section in the Build UI

**DO NOT use `SmartTaskCompletionEnabled: true`** — that was the deprecated Enhanced Task Completion (ETC) flag
from the old experimental orchestrator. It is being removed.

---

## 2. YAML Format (settings.mcs.yml)

### Full working template

```yaml
displayName: My Agent
schemaName: Default_MyAgent_xxxxx
accessControlPolicy: GroupMembership
authenticationMode: Integrated
authenticationTrigger: Always
configuration:
  recognizer:
    $kind: CLICopilotRecognizer
  agentSettings:
    $kind: AgentSettings
    instructions:
      $kind: Instructions
      segments:
        - $kind: StaticSegment
          value: >-
            Your instructions here. Plain text only. No markdown escaping.
            Use >- block scalar to avoid embedded newline tokens in the YAML.
    model:
      $kind: ModelConfig
      series: Opus48
publishedOn: 2026-01-01T00:00:00.0000000Z
template: cliagent-1.0.0
language: 1033
```

### Model series values (confirmed working)

| Series value | Model |
|---|---|
| `Opus48` | Claude Opus 4.8 |
| `Opus47` | Claude Opus 4.7 |
| `Opus46` | Claude Opus 4.6 |
| `Sonnet45` | Claude Sonnet 4.5 |
| `Haiku45` | Claude Haiku 4.5 |

### Critical rules for the instructions value

1. **Plain ASCII only** — no escaped underscores (`\_`), no Unicode zero-width chars (U+200B, U+200C)
2. These cause `BotDefinitionOverride contains invalid YAML` at runtime
3. Use `>-` (block scalar, strip) for multi-line instructions — avoids embedded newline tokens
4. Keep `segments` as a single-element array — multi-segment has known parsing quirks
5. When writing via PowerShell, use `[System.IO.File]::WriteAllText()` with UTF8 — NOT `Set-Content` (can add BOM)
6. **Do NOT use `pac copilot pull` output as an editing base** — pull collapses YAML lines (see Section 3)

---

## 3. PAC CLI Bugs and Workarounds

As of PAC CLI version 2.8.1, the following bugs affect `cliagent-1.0.0` workspaces:

| Bug | Symptom | Workaround |
|-----|---------|-----------|
| `pac copilot push` crash | `System.ArgumentOutOfRangeException` on any `cliagent-1.0.0` workspace when modifying `settings.mcs.yml` | Use **Dataverse API PATCH** (Section 4) |
| `pac copilot pull` collapses YAML | `$kind: CLICopilotRecognizer  agentSettings:` on one line; `series: Opus48publishedOn:` merged | Never use pull output as editing base — always write `settings.mcs.yml` fresh from template |
| `pac copilot push` wipes tools | Connector tools added via UI get overwritten on next push | **NEVER run `pac push` if agent has manually-added connector tools** — use Dataverse API PATCH for config only |
| Skills not visible in PAC CLI | No `pac copilot list-skills` or push-skill command exists | Add skills via Dataverse API (Section 6) or CDP (Section 7) |
| `/agents/designer/<botId>` URL 404s | "Page not found" even for valid agent IDs | Use `/agents/<botId>` — the `/designer/` variant is dead in the new UI |

### Safe PAC CLI operations (still OK)

- `pac auth create` — authenticate to environment
- `pac copilot list` — list agents (read-only)
- `pac copilot push` — pushing **action files only** works fine; avoid pushing `settings.mcs.yml`
- `pac copilot publish --bot <botId>` — publish after Dataverse API changes
- `pac solution pack/unpack` — solution zip operations

### Deployment sequence that avoids all known PAC CLI bugs

```
1. pac copilot init --name "AgentName" --publisher-prefix "prefix"
2. Write settings.mcs.yml from template (Section 2) — do NOT use pac pull output
3. pac copilot pack  ->  produces solution zip
4. pac solution import --path solution.zip --publish-changes
5. pac copilot clone --bot <new-bot-id>  (get synced workspace)
6. Copy actions/*.mcs.yml into clone workspace
7. pac copilot push --project-dir <clone-dir>  (action files only — OK)
8. Update instructions / model via Dataverse API PATCH (Section 4)
9. pac copilot publish --bot <botId>
10. Add skills via Dataverse API (Section 6) or CDP (Section 7)
```

---

## 4. Dataverse API — Updating Agent Configuration

The only safe way to update new orchestrator agent configuration without risking tool loss.

```powershell
# Step 1: Get Dataverse token
$orgUrl   = "https://<orgName>.api.crm.dynamics.com"
$botId    = "<your-bot-guid>"
$dvToken  = (az account get-access-token --resource "https://<orgName>.crm.dynamics.com" | ConvertFrom-Json).accessToken

$headers  = @{
    Authorization      = "Bearer $dvToken"
    "Content-Type"     = "application/json"
    "OData-MaxVersion" = "4.0"
    "OData-Version"    = "4.0"
}

# Step 2: Query current bot configuration
$getUrl  = "$orgUrl/api/data/v9.2/bots?`$filter=botid eq '$botId'&`$select=botid,configuration"
$botData = (Invoke-RestMethod -Uri $getUrl -Headers $headers).value[0]
$config  = $botData.configuration | ConvertFrom-Json

# Step 3: Set recognizer
$config.recognizer = [PSCustomObject]@{ '$kind' = 'CLICopilotRecognizer' }

# Step 4: Set model
$config.agentSettings.model = [PSCustomObject]@{
    '$kind' = 'ModelConfig'
    series  = 'Opus48'
}

# Step 5: Set instructions (plain ASCII only)
$instructions = @"
You are [role].
[Instructions here — plain ASCII, no zero-width chars, no escaped underscores.]
"@
$config.agentSettings.instructions.segments[0].value = $instructions

# Step 6: PATCH back
$patchUrl  = "$orgUrl/api/data/v9.2/bots($botId)"
$patchBody = @{ configuration = ($config | ConvertTo-Json -Depth 20 -Compress) } | ConvertTo-Json
$patchHdrs = $headers + @{ "If-Match" = "*"; "MSCRM.MergeLabels" = "true" }
Invoke-RestMethod -Method Patch -Uri $patchUrl -Headers $patchHdrs -Body $patchBody
Write-Host "Config patched."

# Step 7: Publish
pac copilot publish --bot $botId
```

### Common PATCH failures

| Error | Cause | Fix |
|-------|-------|-----|
| 412 Precondition Failed | Missing `If-Match: *` header | Always include `"If-Match" = "*"` in PATCH headers |
| 401 Unauthorized | Token for wrong resource | Token must target `<orgName>.crm.dynamics.com`, not `management.azure.com` |
| Config silently ignored | Unicode chars in instructions | Strip all non-ASCII before patching |
| 400 Bad Request | `configuration` field not a string | Use `ConvertTo-Json -Compress` then wrap in outer JSON object |

---

## 5. Tools: Direct Connectors and Workflows

The new orchestrator supports two tool types:

- **Direct connector actions** — call a connector operation directly (e.g. Power BI `ExecuteDatasetQuery`).
  Simpler, no PA license required.
- **Workflows** — the native PA flow experience for new orchestrator agents. Supports complex logic,
  multi-step orchestration, and external integrations.

**Note on legacy PA flows:** Classic PA flows wired as `InvokeFlowTaskAction` hit HTTP 500 in some managed
environments. Prefer direct connector actions or Workflows instead.

### Adding tools via UI

Navigate to: `Agents -> <agent> -> Tools -> "+" -> Connectors`

### Verify tools via Dataverse API

```powershell
$compUrl    = "$orgUrl/api/data/v9.2/botcomponents"
$compUrl   += "?`$filter=_parentbotid_value eq '$botId'&`$select=name,componenttype,content"
$components = (Invoke-RestMethod -Uri $compUrl -Headers $headers).value
$components | Select-Object name, componenttype | Format-Table -AutoSize
# Component type 6 = Tool definition
```

### Connection references

After adding connector tools, connection references (connrefs) must be established:

1. First use prompts "Sign in" in the Copilot Studio UI
2. Record connref GUIDs in `LEARNINGS.md` (Section 11) — reuse across agent deployments
3. Connrefs persist per environment, not per agent

### Action file format (for Workflow-based tools)

```yaml
mcs.metadata:
  componentName: MyTool
kind: TaskDialog
inputs:
  - kind: AutomaticTaskInput
    propertyName: text
    name: InputParam
    description: Description of this input. Do NOT use defaultValue — causes publish failures.
outputs:
  - propertyName: outputresult
modelDisplayName: My Tool Display Name
modelDescription: What this tool does and when to use it. Be specific — the reasoning loop reads this.
action:
  kind: InvokeFlowTaskAction
  flowId: <flow-guid>
  connectionProperties:
    $kind: ConnectionProperties
    mode: Invoker
outputMode: All
```

**Important:** `defaultValue` on `AutomaticTaskInput` causes publish failures. Put defaults in the
description or instructions instead.

---

## 6. Skills: Adding via Dataverse API

Skills are `botcomponent` records in Dataverse with `componenttype: 9`. Create directly via API — no
browser automation needed.

```powershell
function Add-AgentSkill {
    param($orgUrl, $botId, $agentSchemaName, $skillName, $skillDescription, $skillInstructions)

    $dvToken   = az account get-access-token --resource $orgUrl --query accessToken -o tsv
    $dvHeaders = @{
        Authorization      = "Bearer $dvToken"
        "Content-Type"     = "application/json"
        "OData-MaxVersion" = "4.0"
        "OData-Version"    = "4.0"
        "Prefer"           = "return=representation"
    }

    # Build data YAML matching the format stored in Dataverse
    $dataYaml  = "kind: InlineAgentSkill`ncontent: |`n"
    $dataYaml += "  ---`n  name: $skillName`n  description: $skillDescription`n  ---`n"
    $dataYaml += "  <!-- bic:source=blank -->`n"
    foreach ($line in $skillInstructions -split "`n") { $dataYaml += "  $line`n" }

    $body = @{
        name          = $skillName
        description   = $skillDescription
        schemaname    = "$agentSchemaName.skill.$skillName"
        componenttype = 9
        data          = $dataYaml
        "parentbotid@odata.bind" = "/bots($botId)"
    } | ConvertTo-Json -Depth 5

    $result = Invoke-RestMethod "$orgUrl/api/data/v9.2/botcomponents" -Method POST -Headers $dvHeaders -Body $body
    Write-Host "Created skill: $($result.name) (ID: $($result.botcomponentid))"
    return $result.botcomponentid
}
```

After adding all skills: `pac copilot publish --bot $botId`

### Skip-if-exists pattern

```powershell
$dvToken    = az account get-access-token --resource $orgUrl --query accessToken -o tsv
$dvHeaders  = @{ Authorization = "Bearer $dvToken"; "Content-Type" = "application/json" }
$components = (Invoke-RestMethod `
    "$orgUrl/api/data/v9.2/botcomponents?`$filter=_parentbotid_value eq '$botId'&`$select=name,componenttype,schemaname" `
    -Headers $dvHeaders).value
$existingSkillNames = ($components | Where-Object { $_.componenttype -eq 9 }).name

if ($existingSkillNames -notcontains $skillName) {
    Add-AgentSkill @params
} else {
    Write-Host "Skill '$skillName' already exists — skipping."
}
```

### What the solution looks like after pac clone

After `pac copilot clone`, skills appear as separate `.mcs.yml` files under `skills/` in the workspace.
Each has `kind: InlineAgentSkill` at root with a `content` block containing the YAML frontmatter and instructions.

### Skill file format (for UI upload)

```markdown
---
name: my-skill-name
description: What this skill provides and when the agent should consult it. Max 1024 chars.
---

[Instructions or structured knowledge here]

## Guidelines
- [Key constraint]

## Examples
**Example: [scenario]**
- User request: "[question]"
- Expected behavior: [what agent should do]
```

Upload via UI: Skills section -> "+" -> "Upload a skill" -> drag .md file (must have YAML frontmatter with
`name` and `description`).

---

## 7. CDP Browser Automation

Skills and the "create connection" step for connector tools cannot be automated via PAC CLI. Use CDP
(Chrome DevTools Protocol) with Edge in remote debugging mode.

### CDP setup

```powershell
# Launch Edge with remote debugging — dedicated profile, never the user's Default profile
$profilePath = "$env:LOCALAPPDATA\CopilotStudioCDP\<profileName>"
Start-Process "msedge.exe" -ArgumentList @(
    "--remote-debugging-port=9333",
    "--user-data-dir=$profilePath",
    "--no-first-run"
)
```

**IMPORTANT:** Never use the user's main Edge profile (`Default`) — it corrupts their browsing session.

### Navigation URLs

```
# Preview environment
https://copilotstudio.preview.microsoft.com/environments/<envId>/agents/<botId>

# Production environment
https://copilotstudio.microsoft.com/environments/<envId>/agents/<botId>
```

Use `/agents/<botId>`. The `/bots/<botId>/overview` URL redirects to new-agent creation.
The `/agents/designer/<botId>` URL returns 404.

### React form fields — critical

Native DOM property setters (`element.value = 'x'`) do **not** trigger React state. Use:

```javascript
// Set value and trigger React state
function reactSet(element, value) {
    element.focus();
    document.execCommand('insertText', false, value);
}

// Clear then set
function reactSetClear(element, value) {
    element.focus();
    document.execCommand('selectAll', false, null);
    document.execCommand('insertText', false, value);
}
```

### Adding a skill via CDP

1. Navigate to agent -> Skills tab
2. Click "+" -> "Create from blank" (or "Add skill")
3. Fill Name (INPUT) using `reactSet`
4. Fill Description (TEXTAREA) using `reactSet`
5. Fill Instructions (TEXTAREA) using `reactSetClear`
6. Click "Create" / "Save" — wait for confirmation toast
7. Verify skill appears in skill list

### Polling for page stability

```javascript
let prev = 0, stable = 0;
const interval = setInterval(() => {
    const len = document.body.innerText.length;
    if (len === prev) { stable++; if (stable >= 2) { clearInterval(interval); resolve(); } }
    else { prev = len; stable = 0; }
}, 10000);
```

---

## 8. Instructions Design

### Principles

- **Instructions = tool routing + operational rules + output format.** Domain knowledge (schemas, column
  names, business rules for a specific dataset) belongs in Skills, not instructions.
- **Plain ASCII only** — no escaped underscores (`\_`), no zero-width Unicode. Either causes a runtime YAML error.
- **One static segment** — keep `segments` as a single-element array.
- **Generic-first** — write instructions that work with any dataset in the domain. Swap Skills for a new
  schema without touching agent configuration.

### Structural template

```
You are a [role] agent.

## Scope
[What the agent does and does not do.]

## Tool Routing
- Use [Tool A] for [purpose].
- Use [Tool B] for [purpose].
- Do NOT call [Tool C] — [reason].

## Operational Rules
- [Rule 1]
- [Rule 2]
- Self-correction: If a tool call returns an error or implausible result, reformulate and retry up to 3 times.

## Output Format
- Lead with the direct answer.
- Follow with supporting detail.
- End with 3 suggested follow-up questions.
```

### What belongs where

| Content | Instructions | Skill |
|---|---|---|
| Tool routing (which tool for what) | Yes | |
| External IDs (workspace, dataset, endpoint GUIDs) | Yes | |
| Domain-agnostic protocol rules | Yes | |
| Output format rules | Yes | |
| Column names, types, sample values | | Yes |
| Domain-specific business rules | | Yes |
| Known patterns for domain question types | | Yes |
| Business conclusions | Never | Never |

---

## 9. Tool Descriptions

Tool descriptions are shown to the reasoning loop to aid tool selection. Domain-aware descriptions improve accuracy.

- **Be specific**: state what the tool does, what it accepts, what it returns, and when to use it.
- **Include format hints**: e.g. "returns JSON with rows array", "accepts DAX EVALUATE statement".
- **Contrast with similar tools**: help the model choose between tools with overlapping scope.
- **Never use `defaultValue`** on `AutomaticTaskInput` — it causes publish failures. Put defaults in the description.

---

## 10. File Delivery

New orchestrator agents run in a **container with bash and Python available out of the box**. Primary
delivery requires no connector tools.

### Primary path: container -> download link

```
Agent generates file in container (bash or python):
  -> HTML report with Chart.js and click-to-filter interactivity
  -> CSV / JSON / Markdown
  -> PPTX via python-pptx
Delivered as a download link directly in chat. No connector tools needed.
```

Instructions to include:

```
When asked for a report or file:
Generate it in your container using bash or python.
Deliver it as a download link in chat.
Every delivery uses a new timestamped filename.
When updating a prior report, carry over all prior content, apply the change,
and re-deliver as a new file — the user always needs a fresh download link.
For visual HTML reports: Chart.js charts, click-to-filter on all tables,
title bar with agent name and date, executive summary (3-5 key findings),
one section per area (narrative + chart + table), footer with data freshness note.
For presentations: PPTX via python-pptx. Slide 1: title + summary.
One slide per area. Final slide: recommendations.
Never output raw HTML or code blocks inline in chat.
```

### Optional path: SharePoint connector

1. Add **OneDrive for Business "Create file"** connector tool (Tools -> "+" -> Connectors)
2. Add target path to instructions: `If a SharePoint tool is available, save to /sites/<Site>/Shared Documents/Reports/<filename> and return the path.`
3. User must authorize connector on first use (consent flow in chat)
4. For binary files (true `.pptx`), use container delivery — "Create file" accepts text content only

---

## 11. LEARNINGS.md Pattern

Every agent project should have a `LEARNINGS.md` (not committed to source) tracking environment-specific
values that cannot be derived from code.

### Template

```markdown
# <Agent Name> — Learnings

## Environment
- Org URL: https://<orgName>.api.crm.dynamics.com
- Environment ID: <envId>
- Bot ID: <botId>
- Bot Schema Name: Default_<AgentName>_<suffix>
- Publisher prefix: <prefix>

## Connection References
| Connector | Connection Ref GUID | Notes |
|-----------|--------------------|----|
| Power BI  | <connref-guid>     | Created <date> |
| OneDrive  | <connref-guid>     | Created <date> |

## Skills Deployed
| Skill Name  | Dataverse Component ID | Last Updated |
|-------------|----------------------|---|
| schema-core | <guid>               | <date> |

## PAC Auth Profile
- Profile name: <profile-alias>
- Environment: <env-guid>

## Known Issues
- [date] [issue description and resolution]

## Deploy Sequence Last Run
- [date] Steps completed: 1-10
```

---

## 12. New Generative Orchestrator vs CGO

| Aspect | CGO | New Generative Orchestrator |
|--------|-----|-----------------------------|
| Recognizer | `GenerativeAIRecognizer` | `CLICopilotRecognizer` |
| Schema | `default-2.1.0` | `cliagent-1.0.0` |
| Configuration | Topics + flows + settings.mcs.yml | settings.mcs.yml only (Tools + Skills) |
| Reasoning | Hidden | Visible as intermediate steps in chat |
| Tool types | PA flows (`InvokeFlowTaskAction`) | Direct connectors + Workflows |
| Skills | Knowledge sources only | Dedicated Skills section |
| PAC CLI support | Full | Partial (push crash on settings; no skill commands) |
| Model | Various | Anthropic Claude series (requires license) |
| Topics | Required | None |
| `SmartTaskCompletionEnabled` | Legacy ETC flag | Deprecated — do not use |

---

## 13. Platform Status and Known Gaps

### CDX / agenticruntime outage pattern

If an agent that was working previously suddenly fails on every request with no YAML or config change,
check CDX platform status before debugging YAML.

**Symptoms of platform outage (not a config error):**
- All agents in the environment fail simultaneously
- Error references `agenticruntime`, `orchestration service`, or generic 500/503
- The same agent worked recently with no changes made

**Distinguish from real YAML errors:**
- Real YAML error: specific message mentioning `BotDefinitionOverride`, affects one agent, persists after redeploy
- Platform outage: affects all agents, resolves without any changes, visible on Microsoft 365 Service Health

**Response:**
1. Check [Microsoft 365 Service Health](https://admin.microsoft.com/adminportal/home#/servicehealth)
2. Wait 15-30 min before debugging YAML
3. Test with a trivial message ("say hello") to isolate reasoning loop vs tool failures

### New Copilot Studio UI navigation

- Old-style URL `/bots/<botId>/overview` redirects to the new-agent creation page
- Correct URL: `/agents/<botId>`
- Build tab (right panel) sections: Model, Microsoft IQ, Skills, Tools, Knowledge, Connected agents, Memory
- Models dropdown: Claude Sonnet 4.6 (default), Opus 4.6, Opus 4.7, Opus 4.8 (experimental)

---

## 14. Quick Reference Checklist

### New agent deployment

- [ ] `pac copilot init --name "AgentName" --publisher-prefix "prefix"`
- [ ] Write `settings.mcs.yml` from template (Section 2) — do NOT use `pac pull` output
- [ ] Use `[System.IO.File]::WriteAllText()` for any file containing instructions
- [ ] Push action files only via PAC CLI (avoid pushing `settings.mcs.yml`)
- [ ] Update config via Dataverse API PATCH (Section 4) — NOT `pac copilot push`
- [ ] Add tools via Copilot Studio UI: Tools -> "+" -> Connectors
- [ ] Add skills via Dataverse API `Add-AgentSkill` (Section 6)
- [ ] `pac copilot publish --bot <botId>`
- [ ] Verify tools in Dataverse API (Section 5)
- [ ] Record connref GUIDs in `LEARNINGS.md` (Section 11)

### Debugging runbook

| Symptom | First check | Fix |
|---------|-------------|-----|
| `System.ArgumentOutOfRangeException` on push | PAC CLI bug on settings.mcs.yml | Use Dataverse API PATCH (Section 4) |
| `BotDefinitionOverride contains invalid YAML` | Non-ASCII in instructions | Strip zero-width chars, remove `\_` escapes |
| Tools missing after push | `pac push` wiped connector tools | Use Dataverse API PATCH only; re-add tools via UI |
| Skill not visible after adding | PAC CLI has no skill sync | Add via Dataverse API (Section 6) or CDP (Section 7) |
| `/agents/designer/<id>` returns 404 | Wrong URL pattern | Use `/agents/<botId>` |
| Agent fails for all users, no YAML change | Platform outage | Check Microsoft 365 Service Health (Section 13) |
| `pac pull` output unreadable | YAML collapse bug | Ignore pull output; write settings from template |
| 412 Precondition Failed on PATCH | Missing header | Add `"If-Match" = "*"` to PATCH headers |
| 401 Unauthorized on PATCH | Wrong token resource | Token must target `<orgName>.crm.dynamics.com` |
