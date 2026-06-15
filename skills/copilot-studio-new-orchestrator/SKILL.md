---
name: "copilot-studio-new-orchestrator"
description: "Learnings, YAML format, gotchas, and deployment patterns for Copilot Studio new orchestrator (cliagent-1.0.0 / CLICopilotRecognizer). Covers settings format, skills, tools, PAC CLI bugs, Dataverse API workarounds, and what NOT to do."
---

# Copilot Studio New Orchestrator — Deployment Learnings

Accumulated from hands-on deployment of a NL2Query agent (Fabric Analyst) using the new Copilot Studio orchestrator. Sources: live UI exploration via CDP, pac copilot clone, Dataverse API inspection, ETC reference sample (outdated — do not use as primary reference).

---

## What the New Orchestrator Actually Is

The new orchestrator (visible in the new Copilot Studio UI as the default mode) uses:
- `recognizer.$kind: CLICopilotRecognizer` — NOT GenerativeAIRecognizer, NOT CLIAgentRecognizer
- `template: cliagent-1.0.0` — NOT default-2.1.0
- No topics — only Tools (flows/MCP connectors) and Skills (structured instructions)
- Reasoning loop handles orchestration, self-correction, parallel tool calls natively
- Skills section is SEPARATE from Knowledge in the UI

**DO NOT use `SmartTaskCompletionEnabled: true`** — that was the deprecated Enhanced Task Completion (ETC) flag from the old experimental orchestrator. It is being deprecated.

---

## Correct settings.mcs.yml Format

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
          value: Your instructions here. Plain text only. No markdown escaping.
    model:
      $kind: ModelConfig
      series: Opus48
publishedOn: 2026-01-01T00:00:00.0000000Z
template: cliagent-1.0.0
language: 1033
```

**CRITICAL — Instructions value rules:**
- Must be plain ASCII — NO escaped underscores (\\_), NO zero-width unicode chars (U+200B, U+200C)
- These characters cause "BotDefinitionOverride contains invalid YAML" at runtime
- When writing via PowerShell, use `[System.IO.File]::WriteAllText()` with UTF8 encoding — NOT Set-Content (which can add BOM or mangle unicode)
- Do NOT use PAC pull result directly — the pull output collapses multiple YAML lines onto one line (PAC CLI bug with cliagent-1.0.0), making the file unreadable and causing push crashes

---

## PAC CLI Known Bugs (version 2.8.1)

**`pac copilot push` crashes with `System.ArgumentOutOfRangeException`** on ANY cliagent-1.0.0 workspace. This affects all settings.mcs.yml modifications. The crash is a PAC CLI bug, not a YAML error on your part.

**Workaround for instructions/model changes:** Update via Dataverse API directly:
```powershell
$token = az account get-access-token --resource https://orgea8005ed.crm.dynamics.com --tenant <tenantId> --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json"; "OData-MaxVersion" = "4.0"; "OData-Version" = "4.0"; "If-Match" = "*" }
$bot = (Invoke-RestMethod "https://<orgurl>/api/data/v9.2/bots?`$filter=schemaname eq '<schemaname>'&`$select=botid,configuration" -Headers $headers).value[0]
$config = $bot.configuration | ConvertFrom-Json
# Modify $config properties here
$body = @{ configuration = ($config | ConvertTo-Json -Depth 20 -Compress) } | ConvertTo-Json
Invoke-RestMethod "https://<orgurl>/api/data/v9.2/bots($($bot.botid))" -Method PATCH -Headers $headers -Body $body
```
Then: `pac copilot publish --bot <botId>`

**`pac copilot pull` collapses YAML lines** — the output has `$kind: CLICopilotRecognizer  agentSettings:` on one line and `series: Opus48publishedOn:` merged. Do not use this output as a base for editing. Always write settings from scratch after a pull.

**Actions (tools) CAN be pushed** using the standard `InvokeFlowTaskAction` format — same as Classic Generative agents. The crash is specific to settings.mcs.yml parsing.

---

## Correct Action File Format (Tools)

```yaml
mcs.metadata:
  componentName: ExecuteDAX
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
outputs:
  - propertyName: daxqueryresults
modelDisplayName: Execute DAX
modelDescription: Executes a DAX query. Returns results as plain text.
action:
  kind: InvokeFlowTaskAction
  flowId: <flow-guid>
  connectionProperties:
    $kind: ConnectionProperties
    mode: Invoker
outputMode: All
```

Note: `defaultValue` on AutomaticTaskInput causes publish failures — do not use. Put defaults in the description or agent instructions instead.

---

## Skills in the New Orchestrator

Skills are NOT knowledge sources. They appear in a separate "Skills" section in the Build UI.

**Upload format (.md file with YAML frontmatter):**
```markdown
---
name: my-skill-name
description: What the skill does and when to use it (required, 1024 char max)
---

When this skill is activated:

1. [Step or instruction]
2. [Step or instruction]

## Guidelines
- [Key constraint]

## Examples
**Example 1: [scenario]**
- User request: "[question]"
- Expected behavior: [what agent should do]
```

**To upload via UI:** Skills section → "+" → "Upload a skill" → drag .md file. File must have YAML frontmatter with both `name` and `description` fields.

**To create via UI (CDP automatable):** Skills "+" → "Create from blank" → fill Name (INPUT), Description (TEXTAREA), Instructions (TEXTAREA) → Create. Use `document.execCommand('insertText', false, value)` to trigger React state — native DOM setter does NOT work.

**PAC CLI has no skill command** — skills cannot be pushed via `pac copilot push`. UI only.

---

## Deployment Pattern That Works

The `pac copilot push` crash on settings means the correct deployment flow for new orchestrator agents is:

```
1. pac copilot init --name "AgentName" --publisher-prefix "prefix"
2. (Remove actions/ and connectionreferences.mcs.yml from init workspace)
3. pac copilot pack → produces solution zip
4. pac solution import --path solution.zip --publish-changes
5. pac copilot clone --bot <new-bot-id> → get synced workspace
6. Copy actions/*.mcs.yml and connectionreferences.mcs.yml into clone
7. pac copilot push --project-dir <clone-dir>   ← actions push OK
8. Update instructions/model via Dataverse API PATCH
9. pac copilot publish --bot <bot-id>
10. Add skills via UI (or CDP automation)
```

---

## New UI Navigation Notes

The new Copilot Studio UI (preview.microsoft.com) uses different URL patterns:
- Old UI agents: `/bots/<botId>/overview`  
- New UI agents: `/agents/<botId>`  

When navigating to an old-style URL for a new orchestrator agent, the UI redirects to `/agents/new` (creates a new agent) instead of opening the existing one. Use the `/agents/<botId>` URL format.

---

## What the New UI Shows (Build Tab)

Right panel sections in order:
- **Model** — dropdown: Claude Sonnet 4.6 (default), Opus 4.6, Opus 4.7, Opus 4.8 (experimental)
- **Microsoft IQ** — work context integration
- **Skills** — "Define behaviors through structured instructions"
- **Tools** — "Connect the agent to external systems and actions" (shows connected flows)
- **Knowledge** — "Provide trusted context to guide decisions"
- **Connected agents** — multi-agent orchestration
- **Memory** — toggle for conversation memory

Tools section shows PA flows by their display name (e.g. "TableTalk - Fabric - Send DAX Query") once connected via InvokeFlowTaskAction.

---

## Sources

- Live Copilot Studio UI exploration (new UI, CDX environment) — June 2026
- `pac copilot clone` output analysis for `d01d7579-bf47-4da7-b751-22a419ade844` (Fabric Analyst)
- Dataverse API inspection of bot configuration JSON
- ETC sample repo `microsoft/enhanced-task-completion` — NOTE: outdated as of June 2026, uses deprecated `SmartTaskCompletionEnabled` pattern
- Dracarys dashboard `C:\Users\kkanjitajdin\OneDrive - Microsoft\Documents\Clawpilot\dracarys-dashboard\dracarys-dashboard.html` — design guidance and feature notes
- PAC CLI 2.8.1 crash logs at `C:\Users\kkanjitajdin\.nuget\packages\microsoft.powerapps.cli\2.8.1\tools\logs\pac-log.txt`

