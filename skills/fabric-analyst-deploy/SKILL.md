---
name: "fabric-analyst-deploy"
description: "Full end-to-end deployment skill for Fabric Analyst (NGO / new Copilot Studio orchestrator). Creates agent via PAC CLI + Dataverse API — NO manual UI step needed. Sets up ContosoRetail dataset, adds Power BI connector tools via CDP browser, adds skills, publishes, tests with screenshot. Asks 4 questions upfront, skips phases that already exist, lists what NGO needs to get better."
---

# Fabric Analyst — Full Deployment Skill (NGO)

Deploy the **Fabric Analyst** agent (NGO architecture) into any Power Platform environment with Copilot Studio on Early Release. Fully autonomous after 4 upfront questions.

**No manual UI agent creation needed.** The agent shell is created via PAC CLI + Dataverse API. Only the Tools and Skills steps require a CDP browser session (UI-only operations in Copilot Studio).

**Architecture:** NGO uses `CLICopilotRecognizer` + `cliagent-1.0.0`. No topics — only Tools, Skills, and a reasoning loop. See `/copilot-studio-new-orchestrator` and `/ngo-nl2query-patterns` for format reference and known bugs.

**Credit:** TableTalk with Fabric (CGO reference agent) by [Nico Sprotti](https://github.com/NicoPilot-dev/TableTalkWithFabric). The ContosoRetail dataset and Fabric Analyst NGO agent were built by the Microsoft CAT team.

---

## Ask these 4 questions FIRST

```
1. What local working folder should I use? (default: C:\src\FabricAnalyst)
2. What is your Copilot Studio environment URL?
   Format: https://copilotstudio[.preview].microsoft.com/environments/<envId>/home
3. What email are you signed in with in Power Platform?
4. Do you have Power BI Pro or higher?
```

Extract `$envId` from the environment URL. Derive `$orgUrl` in Phase 0.

---

## LEARNINGS.md — check at start, update at end

Before doing any work, check for a learnings file in the working directory:

```powershell
$learnFile = "$workDir\LEARNINGS.md"
if (Test-Path $learnFile) {
    $learnings = Get-Content $learnFile -Raw
    Write-Host "=== Existing learnings ==="
    Write-Host $learnings
    # Extract known IDs if present (skip creation phases if IDs found and valid)
    if ($learnings -match 'botId:\s*(\S+)') { $botId = $Matches[1]; Write-Host "Known bot: $botId" }
    if ($learnings -match 'workspaceId:\s*(\S+)') { $workspaceId = $Matches[1] }
    if ($learnings -match 'datasetId:\s*(\S+)') { $datasetId = $Matches[1] }
}
```

At end of each run, write/update the learnings file:

```powershell
$learnContent = @"
# Fabric Analyst — Session Learnings
Last updated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')
User: $email
Environment: $envId

## Discovered IDs
- envId: $envId
- orgUrl: $orgUrl
- botId: $botId
- workspaceId: $workspaceId
- datasetId: $datasetId
- tenantId: $tenantId

## Session Notes
- $(Get-Date -Format 'yyyy-MM-dd'): Deployment run completed. Tools: Run a query, Run a json query, Create file. Skills: schema-definitions, dax-patterns-customer, dax-patterns-marketing.
"@
$learnContent | Set-Content $learnFile -Encoding UTF8
Write-Host "Learnings saved to $learnFile"
```

---

## Skip-if-exists logic

Check these before each phase:

```powershell
# Skip auth if PAC CLI already has a profile for this email
if (& $pac auth list | Select-String $email) {
    Write-Host "Auth profile exists for $email — skipping auth create"
}

# Skip workspace creation if workspace_id.txt exists
if (Test-Path "$workDir\workspace_id.txt") {
    $workspaceId = Get-Content "$workDir\workspace_id.txt"
    Write-Host "Workspace exists: $workspaceId — skipping creation"
}

# Skip dataset creation if dataset_id.txt exists AND queryable
if (Test-Path "$workDir\dataset_id.txt") {
    $datasetId = Get-Content "$workDir\dataset_id.txt"
    $q = @{ queries = @(@{ query = "EVALUATE ROW(`"n`", COUNTROWS(dim_customers))" }) } | ConvertTo-Json -Depth 5
    $r = Invoke-RestMethod -Method POST `
        -Uri "https://api.powerbi.com/v1.0/myorg/groups/$workspaceId/datasets/$datasetId/executeQueries" `
        -Headers $headers -Body $q -ErrorAction SilentlyContinue
    if ($r) { Write-Host "Dataset exists and queryable — skipping dataset creation" }
    else { Write-Host "Dataset ID found but not queryable — recreating" }
}

# Skip agent creation if already in environment
$existingBot = & $pac copilot list | Select-String "Fabric Analyst"
if ($existingBot) {
    $botId = ($existingBot -split "\s+")[1]
    Write-Host "Agent exists (ID: $botId) — skipping creation, will update config"
}

# Always re-run Phase 4 (Dataverse API config) and publish to apply any changes
```

---

## PHASE 0 — Prerequisites

```powershell
$workDir = "C:\src\FabricAnalyst"   # or user-provided folder
New-Item -ItemType Directory -Path $workDir -Force | Out-Null

# PAC CLI — find or install
$pac = (Get-ChildItem "$env:USERPROFILE\.nuget\packages\microsoft.powerapps.cli" `
    -Recurse -Filter "pac.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
if (-not $pac) {
    dotnet tool install --global Microsoft.PowerApps.CLI.Tool
    $pac = (Get-ChildItem "$env:USERPROFILE\.nuget\packages\microsoft.powerapps.cli" `
        -Recurse -Filter "pac.exe" | Select-Object -First 1).FullName
}
if (-not $pac) { $pac = (Get-Command pac -ErrorAction SilentlyContinue).Source }
Write-Host "PAC CLI: $pac"

# Az CLI — install if missing
az --version 2>$null
if ($LASTEXITCODE -ne 0) { winget install Microsoft.AzureCLI }

# Python — for dataset generation
python --version

# Derive org URL from environment ID
$aadToken = az account get-access-token --resource https://service.powerapps.com/ --query accessToken -o tsv
$envInfo = Invoke-RestMethod `
    "https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform/environments/$envId" `
    -Headers @{Authorization="Bearer $aadToken"}
$orgUrl = $envInfo.properties.linkedEnvironmentMetadata.instanceUrl
Write-Host "Org URL: $orgUrl"
```

---

## PHASE 1 — Auth

```powershell
# PAC CLI — device code (works for any tenant, no hardcoded tenant ID)
& $pac auth create --deviceCode --environment $orgUrl --name "FabricAnalystDeploy"
& $pac auth select --name "FabricAnalystDeploy"

# Az CLI — device code
az login --use-device-code
$tenantId = az account show --query tenantId -o tsv

# Token helpers (called fresh before each API call)
function Get-PBIToken {
    az account get-access-token --resource https://analysis.windows.net/powerbi/api `
        --tenant $tenantId --query accessToken -o tsv
}
function Get-DVToken {
    az account get-access-token --resource $orgUrl `
        --tenant $tenantId --query accessToken -o tsv
}
```

---

## PHASE 2 — Create ContosoRetail dataset


```powershell
$token = Get-PBIToken
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }

# Create workspace (skip if workspace_id.txt exists)
if (-not (Test-Path "$workDir\workspace_id.txt")) {
    $wsBody = @{ name = "Fabric Analyst Demo" } | ConvertTo-Json
    $ws = Invoke-RestMethod "https://api.powerbi.com/v1.0/myorg/groups" `
        -Method POST -Headers $headers -Body $wsBody
    $workspaceId = $ws.id
    $workspaceId | Set-Content "$workDir\workspace_id.txt"
    Write-Host "Workspace created: $workspaceId"
}

# Generate + push ContosoRetail dataset (13 tables, 500 rows each)
# build_dataset.py is generated by this skill — see PHASE 2b below
$token = Get-PBIToken
python "$workDir\build_dataset.py" $token $workspaceId
$datasetId = Get-Content "$workDir\dataset_id.txt"

# Validate
$q = @{ queries = @(@{ query = "EVALUATE ROW(`"rows`", COUNTROWS(dim_customers))" }) } | ConvertTo-Json -Depth 5
$r = Invoke-RestMethod `
    "https://api.powerbi.com/v1.0/myorg/groups/$workspaceId/datasets/$datasetId/executeQueries" `
    -Method POST -Headers $headers -Body $q
Write-Host "dim_customers rows: $($r.results[0].tables[0].rows)"
```

### PHASE 2b — build_dataset.py

Generate `$workDir\build_dataset.py` from the CAT reference implementation. The script:
- Creates a 13-table ContosoRetail push dataset schema via Power BI REST API
- Generates 500 rows per table using Faker (run `pip install faker requests`)
- Pushes all rows to the dataset
- Writes dataset ID to `$workDir\dataset_id.txt`

Tables: `dim_customers`, `dim_products`, `dim_stores`, `dim_employees`, `fact_orders`, `fact_order_items`, `fact_returns`, `fact_inventory`, `fact_marketing_campaigns`, `fact_website_sessions`, `fact_support_tickets`, `fact_supplier_performance`, `fact_store_traffic`.

If the user already has a Power BI dataset they want to use, skip Phase 2 entirely and provide `$workspaceId` and `$datasetId` directly.

---

## PHASE 3 — Create the NGO agent

**Unlike CGO (solution zip from GitHub), the NGO agent is created programmatically. No manual UI step required.**

```powershell
$agentDir = "$workDir\agent-init"
New-Item -ItemType Directory -Path $agentDir -Force | Out-Null

& $pac copilot init `
    --name "Fabric Analyst" `
    --publisher-prefix "fa" `
    --instructions "placeholder" `
    --project-dir $agentDir

# CRITICAL: Remove actions/ and connectionreferences.mcs.yml before packing
# pac copilot pack crashes if these are present for cliagent-1.0.0
Remove-Item "$agentDir\actions" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$agentDir\connectionreferences.mcs.yml" -ErrorAction SilentlyContinue

& $pac copilot pack `
    --publisher-prefix "fa" `
    --project-dir $agentDir `
    --solution-name "FabricAnalystSolution" `
    --output-path $workDir

& $pac solution import `
    --path "$workDir\FabricAnalystSolution.zip" `
    --publish-changes

# Get the new bot ID
$botLine = (& $pac copilot list | Select-String "Fabric Analyst")
$botId = ($botLine -split "\s+")[1]
$botId | Set-Content "$workDir\bot_id.txt"
Write-Host "Bot ID: $botId"
```

---

## PHASE 4 — Configure agent via Dataverse API

**Why Dataverse API and not `pac copilot push`?**
`pac copilot push` crashes with `System.ArgumentOutOfRangeException` on ALL `cliagent-1.0.0` agents when modifying `settings.mcs.yml`. This is a known PAC CLI bug (confirmed 2.8.1). Dataverse API PATCH is the only reliable path.

**CRITICAL: Instructions must be plain ASCII** — no `\_` escaped underscores, no zero-width chars (U+200B/U+200C). These cause `BotDefinitionOverride contains invalid YAML` at agent runtime.

```powershell
$dvToken = Get-DVToken
$dvHeaders = @{
    Authorization   = "Bearer $dvToken"
    "Content-Type"  = "application/json"
    "OData-MaxVersion" = "4.0"
    "OData-Version" = "4.0"
    "If-Match"      = "*"
}

$bot = (Invoke-RestMethod `
    "$orgUrl/api/data/v9.2/bots?`$filter=botid eq '$botId'&`$select=botid,configuration" `
    -Headers $dvHeaders).value[0]
$config = $bot.configuration | ConvertFrom-Json

# Set NGO recognizer
$config.recognizer = [PSCustomObject]@{ '$kind' = 'CLICopilotRecognizer' }

# Set model (Anthropic Claude Opus 4.8 — requires Anthropic license in tenant)
$config.agentSettings.model = [PSCustomObject]@{ '$kind' = 'ModelConfig'; series = 'Opus48' }

# Build instructions — PLAIN ASCII ONLY, no escaped underscores
$instructions = "You are a strategic retail data analyst with access to the ContosoRetail Power BI dataset. " +
    "WorkspaceID: $workspaceId. DatasetID: $datasetId. " +
    "Tables: dim_customers, dim_products, dim_stores, dim_employees, fact_orders, fact_order_items, " +
    "fact_returns, fact_inventory, fact_marketing_campaigns, fact_website_sessions, fact_support_tickets, " +
    "fact_supplier_performance, fact_store_traffic. " +
    "When answering: " +
    "1. Do NOT call RefreshDataset. Data is maintained on an external schedule. " +
    "2. Use EVALUATE TOPN(3, tablename) before aggregating unfamiliar tables. " +
    "3. Write focused DAX queries. Use SUMX(FILTER()) for cross-table joins — no active relationships in push dataset. " +
    "4. Self-correct on DAX errors or implausible results. " +
    "5. Synthesize findings with specific numbers. " +
    "6. After any multi-metric analysis offer: Option A save interactive HTML report to OneDrive. Option B save PPTX outline to OneDrive. " +
    "7. Never output raw code blocks in chat. " +
    "8. End with 3 follow-up questions."

$config.agentSettings.instructions.segments[0].value = $instructions

$body = @{ configuration = ($config | ConvertTo-Json -Depth 20 -Compress) } | ConvertTo-Json
Invoke-RestMethod "$orgUrl/api/data/v9.2/bots($botId)" -Method PATCH -Headers $dvHeaders -Body $body
Write-Host "Agent config updated"
```

---

## PHASE 5 — Add Tools via CDP browser

Launch a dedicated Edge profile for CDP automation. First launch will require the user to sign in to the environment in the browser window — subsequent runs reuse the profile.

```powershell
# Use a dedicated profile — keep separate from the user's main Edge to avoid session conflicts
$profileName = "copilot-studio-cdp"   # change if you want per-environment profiles
$profilePath = "$env:LOCALAPPDATA\CopilotStudioCDP\$profileName"
New-Item -ItemType Directory -Path $profilePath -Force | Out-Null

$edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
Start-Process $edgePath "-ArgumentList" "--remote-debugging-port=9333 --user-data-dir=`"$profilePath`" --no-first-run about:blank"
Start-Sleep -Seconds 5
```

**Sign-in note:** On first launch of a new profile, sign in to your Power Platform account in the Edge window that opens. After sign-in, the profile is saved and all subsequent CDP runs are fully automated.

Navigate to agent Build tab (use envId and botId from Phase 3):
```
https://copilotstudio[.preview].microsoft.com/environments/$envId/agents/$botId
```
Use `.preview.` for Early Release environments, omit `.preview.` for production.

Add these tools via **Tools "+" → Connectors**:

1. **"Run a query against a dataset"** (Power BI) — primary DAX executor
2. **"Run a json query against a dataset"** (Power BI) — DAX variant/fallback
3. **"Create file"** (OneDrive for Business) — for saving HTML reports and PPTX outlines

For each tool: click +, search by name, click the result button, click Add, wait for confirmation.

**Finding the correct "Create file" button** (multiple connectors offer "Create file"):
```javascript
// Run in CDP browser console to identify which button index is OneDrive for Business
[...document.querySelectorAll("button")].filter(b => b.innerText.trim() === "Create file").map((b,i) => {
    var el = b; var found = "";
    for (var j=0; j<10; j++) {
        el = el.parentElement;
        if (el && el.innerText.includes("OneDrive for Business") && el.innerText.includes("Create file")) {
            found = i; break;
        }
    }
    return i + ": " + found;
})
// The index that returns a non-empty found value is the OneDrive for Business button
```

**Verify tools were added:**
```powershell
$dvToken = Get-DVToken
$dvHeaders = @{ Authorization = "Bearer $dvToken"; "Content-Type" = "application/json" }
$components = (Invoke-RestMethod `
    "$orgUrl/api/data/v9.2/botcomponents?`$filter=_parentbotid_value eq '$botId'&`$select=name,componenttype" `
    -Headers $dvHeaders).value
$pbiTools = $components | Where-Object { $_.name -like "*query*dataset*" }
Write-Host "Power BI tools found: $($pbiTools.Count)"
```

---

## PHASE 6 — Add Skills via Dataverse API

**No CDP browser needed.** Skills are `botcomponent` records (componenttype 9) — created via the same Dataverse API used for agent config.

**Solution file format:** `pac copilot clone` captures skills in `translations/<schemaName>.skill.<name>.mcs.yml` with `kind: InlineAgentSkill`. But `pac copilot push/pack` do NOT yet support `translations/` — Dataverse API is the automated write path today.

```powershell
function Add-AgentSkill($skillName, $skillDescription, $skillBody) {
    $dvToken = Get-DVToken
    $h = @{ Authorization = "Bearer $dvToken"; "Content-Type" = "application/json";
             "OData-MaxVersion" = "4.0"; "OData-Version" = "4.0"; "Prefer" = "return=representation" }
    # Skip if already exists
    $existing = (Invoke-RestMethod "$orgUrl/api/data/v9.2/botcomponents?`$filter=_parentbotid_value eq '$botId' and name eq '$skillName'&`$select=name" -Headers $h).value
    if ($existing) { Write-Host "Skill '$skillName' already exists — skipping"; return }
    # Build data YAML
    $indented = ($skillBody -split "`n" | ForEach-Object { "  $_" }) -join "`n"
    $dataYaml = "kind: InlineAgentSkill`ncontent: |`n  ---`n  name: $skillName`n  description: $skillDescription`n  ---`n  <!-- bic:source=blank -->`n$indented"
    $body = @{
        name = $skillName; description = $skillDescription
        schemaname = "${agentSchemaName}.skill.${skillName}"
        componenttype = 9; data = $dataYaml
        "parentbotid@odata.bind" = "/bots($botId)"
    } | ConvertTo-Json -Depth 5
    $r = Invoke-RestMethod "$orgUrl/api/data/v9.2/botcomponents" -Method POST -Headers $h -Body $body
    Write-Host "Created: $($r.name) (ID: $($r.botcomponentid))"
}

# Get agent schema name
$dvToken = Get-DVToken
$h = @{ Authorization = "Bearer $dvToken"; "Content-Type" = "application/json" }
$agentSchemaName = (Invoke-RestMethod "$orgUrl/api/data/v9.2/bots?`$filter=botid eq '$botId'&`$select=schemaname" -Headers $h).value[0].schemaname

# Add schema skill
Add-AgentSkill "schema-definitions" "ContosoRetail schema — tables, column types, join patterns, business rules" "Dataset type: Power BI push dataset. No active relationships — use SUMX(FILTER()) for joins."

# Add DAX patterns skill
Add-AgentSkill "dax-patterns" "Common DAX patterns for NL2Query over ContosoRetail" "Revenue by segment: SUMX(FILTER(fact_orders, fact_orders[customer_id] = dim_customers[customer_id]), fact_orders[order_value])"
```

**Future:** Once PAC CLI supports `translations/`, skills become YAML files in the repo — no Dataverse API needed. The YAML format is already defined (see `/ngo-nl2query-patterns` skill).


## PHASE 7 — Publish

```powershell
& $pac copilot publish --bot $botId
# Expected output: "Published successfully!"
```

If PAC publish fails, use CDP: click the Publish button in the Build tab header.

---

## PHASE 8 — Test and screenshot

In the CDP browser, navigate to the Preview/Test tab and send this question:

> "How many customers are in each segment and what is their average lifetime value?"

Wait up to 90s. Expected behavior:
- Agent runs EVALUATE TOPN(3, dim_customers) to explore schema
- Calls "Run a query against a dataset" with a SUMX(FILTER()) DAX query
- Returns a markdown table with segment counts and avg LTV
- Offers Option A (HTML report) or Option B (PPTX outline)

Save screenshot to `$workDir\test-screenshot.png`.

---

## PHASE 9 — Output summary

Output after all phases complete:

1. **IDs deployed:**
   - Bot ID, workspace ID, dataset ID, environment ID
   - Tools: Run a query, Run a json query, Create file
   - Skills: schema-definitions, dax-patterns-customer, dax-patterns-marketing

2. **20 test questions:**
   1. What tables do you have access to?
   2. Which customer segment drives the most revenue?
   3. Compare marketing channel ROI over time
   4. Which product categories have the highest profit margins?
   5. Which product categories have the highest return rates?
   6. How does the West region compare to other regions in revenue and conversion?
   7. Which suppliers have reliability issues?
   8. What is the trend in email marketing CTR over the last 3 years?
   9. Are there stockout risks? Which categories are most affected?
   10. Do support ticket volumes spike after marketing campaigns?
   11. What is the customer lifetime value by segment?
   12. Which stores are underperforming on conversion rate?
   13. What is the average order value by customer segment?
   14. Compare social vs email campaign ROI month by month
   15. What is revenue split by channel (In-Store vs Online vs Mobile)?
   16. Which day of the week has the highest store traffic conversion?
   17. Are VIP customers more or less likely to return products?
   18. What inventory items are at immediate risk of stockout?
   19. Which campaigns generated the highest revenue lift?
   20. Give me a comprehensive executive summary with top 3 recommendations. Then save an HTML report to my OneDrive.

3. **Update LEARNINGS.md** with all discovered IDs and a session note.

---

## What NGO needs to get better (known platform gaps as of mid-2026)

| Gap | Impact | Workaround used |
|---|---|---|
| PA flows as tools: HTTP 500 in some environments | Blocks tool calls in managed tenants | Use direct connector actions |
| Inline chart rendering: not supported | No charts in chat | Deliver charts as HTML files to OneDrive |
| PAC CLI push crashes on cliagent-1.0.0 | Can't deploy settings via CLI | Use Dataverse API PATCH |
| Skills not accessible via PAC CLI | No automation path | UI-only via CDP browser |
| In-product Evaluation: not available for NGO | Can't run test sets in-product | Use CDP-based point testing (comparison skill) |
| Refresh tool: HTTP 500 in some environments | Dataset can't be refreshed via agent | Disable via instructions, use external schedule |
| No persistent conversation variables | Agent can't carry state across turns | Re-query on each turn |
| /agents/designer/<botId> URL 404s | Broken link pattern | Use /agents/<botId> |

---

## Known pitfalls

| Gotcha | Fix |
|---|---|
| "BotDefinitionOverride contains invalid YAML" | Instructions have escaped underscores (`\_`) or zero-width unicode — use plain ASCII only |
| pac copilot push crashes: ArgumentOutOfRangeException | PAC CLI 2.8.1 bug on cliagent-1.0.0 — use Dataverse API PATCH |
| pac copilot pull collapses YAML | Don't use pull output as edit base — always write settings.mcs.yml fresh |
| Tools show "Can't connect to this tool" | PA flows fail in some envs — use direct connector actions (this skill does that) |
| CDP React fields don't update | Use document.execCommand('insertText') not native value setter |
| Agent URL not found | Use /agents/<botId> NOT /agents/designer/<botId> — /designer/ variant 404s |
| Early Release channel required | NGO only available on Early Release as of mid-2026 |
| ALL agents show InvalidContent error | Platform outage (not your YAML) — check a known-working agent, wait 1-4 hours |
| Anthropic models not available | Requires Anthropic license in tenant — contact admin if Claude series not in model picker |


