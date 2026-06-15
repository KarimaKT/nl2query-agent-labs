---
name: "tabletalk-fabric-deploy"
description: "Full end-to-end deployment skill for TableTalk with Fabric (CGO): install from GitHub, create realistic Contoso Retail dataset, configure agent with correct best practices, test with 20 questions, analyze quality, produce screenshot and user guide. Asks 4 questions upfront, does the rest autonomously. Requires: GitHub repo URL + logged-in Power Platform environment with Copilot Studio."
---

# TableTalk with Fabric — Full Deployment Skill (CGO)

> **This agent was designed and built by [Nico Sprotti](https://github.com/NicoPilot-dev).**
> The solution, all agent logic, topic design, flow architecture, and the "TableTalk" concept are entirely his work.
> Repository: **https://github.com/NicoPilot-dev/TableTalkWithFabric**
>
> This deployment skill automates the setup process (dataset creation, environment configuration, publishing, and testing)
> and was built separately. If you use or share this agent, please credit Nico Sprotti and link to his repo.

Deploy the TableTalk with Fabric Copilot Studio agent into any Power Platform environment with a realistic sample dataset, configured correctly, published, and tested. This skill runs autonomously after 4 upfront questions.

---


---

## LEARNINGS.md — persistent session knowledge

Maintain a LEARNINGS.md in your working directory so discovered IDs and session notes persist across runs:

```powershell
$learnFile = "$workDir\LEARNINGS.md"
# Load at start
if (Test-Path $learnFile) {
    $learnings = Get-Content $learnFile -Raw
    if ($learnings -match 'botId:\s*(\S+)') { $botId = $Matches[1] }
    if ($learnings -match 'workspaceId:\s*(\S+)') { $workspaceId = $Matches[1] }
    if ($learnings -match 'datasetId:\s*(\S+)') { $datasetId = $Matches[1] }
    if ($learnings -match 'flowId:\s*(\S+)') { $flowId = $Matches[1] }
    Write-Host "Loaded prior session IDs from $learnFile"
}

# Write at end
@"
# TableTalk with Fabric — Session Learnings
Last updated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')
User: $email
Environment: $envId

## Discovered IDs
- envId: $envId
- orgUrl: $orgUrl
- botId: $botId
- workspaceId: $workspaceId
- datasetId: $datasetId
- flowId: $flowId

## Session Notes
- $(Get-Date -Format 'yyyy-MM-dd'): Deployment run. Agent: TableTalk with Fabric (CGO).
"@ | Set-Content $learnFile -Encoding UTF8
```

---
## Ask these 4 questions FIRST (nothing else)

```
1. What local folder should I use for files? (default: C:\src\Fabric)
2. What is your Copilot Studio environment URL? (e.g. https://copilotstudio.microsoft.com/environments/<envId>/home)
3. What email address are you signed in with in Power Platform / M365?
4. Do you have Power BI Pro or higher? (needed for workspace creation)
```

Derive from environment URL:
- Environment ID = GUID in URL path
- Tenant ID = run `az account show --query tenantId -o tsv` after az login

## Skip-if-exists logic (check before each phase)

Before running each phase, check if the output already exists and skip if so:

```powershell
# Phase 1: skip clone if repo already cloned
if (Test-Path "$workDir\TableTalkFabric_1_0_0_1.zip") { Write-Host "Repo already cloned — skipping" }

# Phase 1: skip solution import if agent already exists in environment
if (& $pac copilot list | Select-String "TableTalk with Fabric") { Write-Host "Agent already imported — skipping solution import" }

# Phase 3: skip workspace creation if workspace_id.txt exists
if (Test-Path "$workDir\workspace_id.txt") { $workspaceId = Get-Content "$workDir\workspace_id.txt"; Write-Host "Workspace exists: $workspaceId — skipping" }

# Phase 4: skip dataset creation if dataset_id.txt exists AND DAX query succeeds
if (Test-Path "$workDir\dataset_id.txt") {
    $datasetId = Get-Content "$workDir\dataset_id.txt"
    $testQuery = @{ queries = @(@{ query = "EVALUATE ROW(`"n`", COUNTROWS(dim_customers))" }) } | ConvertTo-Json -Depth 5
    $r = Invoke-RestMethod -Method POST -Uri "https://api.powerbi.com/v1.0/myorg/groups/$workspaceId/datasets/$datasetId/executeQueries" -Headers $headers -Body $testQuery -ErrorAction SilentlyContinue
    if ($r) { Write-Host "Dataset exists and queryable — skipping dataset creation" }
    else { Write-Host "Dataset ID found but not queryable — recreating" }
}

# Phase 5: skip agent clone if already cloned
if (Test-Path "$workDir\agent\TableTalk with Fabric\agent.mcs.yml") { Write-Host "Agent already cloned — skipping clone" }
```

Always re-run Phase 5 push+publish to apply any instruction or config changes.

---

## PHASE 0 — Prerequisites

```powershell
# Check/install PAC CLI via NuGet
$pac = (Get-ChildItem "$env:USERPROFILE\.nuget\packages\microsoft.powerapps.cli" -Recurse -Filter "pac.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
if (-not $pac) {
    dotnet tool install --global Microsoft.PowerApps.CLI.Tool
    $pac = (Get-ChildItem "$env:USERPROFILE\.nuget\packages\microsoft.powerapps.cli" -Recurse -Filter "pac.exe" | Select-Object -First 1).FullName
}
if (-not $pac) { $pac = (Get-Command pac -ErrorAction SilentlyContinue).Source }
Write-Host "PAC CLI: $pac"

# Check Az CLI
az --version 2>$null
if ($LASTEXITCODE -ne 0) { winget install Microsoft.AzureCLI }

# Check Python
python --version
```

---

## PHASE 1 — Clone repo and import solution

```powershell
$workDir = "C:\src\Fabric"   # or user-specified
New-Item -ItemType Directory -Path $workDir -Force | Out-Null
git clone https://github.com/NicoPilot-dev/TableTalkWithFabric $workDir --depth 1

# Authenticate PAC CLI with device code
& $pac auth create --deviceCode --environment "https://orgXXXXXXXX.crm.dynamics.com" --name "TableTalkDeploy"
# User enters code at https://microsoft.com/devicelogin — NEVER use Playwright browser for this

# List profiles and select the right one
& $pac auth list
& $pac auth select --index 1   # or the index shown for TableTalkDeploy

# Import solution
$solutionZip = (Get-ChildItem $workDir -Filter "*.zip" | Select-Object -First 1).FullName
& $pac solution import --path $solutionZip --publish-changes
Write-Host "Solution imported"

# Confirm
& $pac copilot list | Select-String "TableTalk"
```

The Dynamics org URL is discoverable via:
```powershell
$token = az account get-access-token --resource https://service.powerapps.com/ --query accessToken -o tsv
$envInfo = Invoke-RestMethod "https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform/environments/$envId" -Headers @{ Authorization = "Bearer $token" }
$orgUrl = $envInfo.properties.linkedEnvironmentMetadata.instanceUrl
```

---

## PHASE 2 — Az CLI auth (Power BI REST API)

```powershell
# Get tenant ID if not known
$tenantId = az account show --query tenantId -o tsv 2>$null
if (-not $tenantId) {
    az login --use-device-code   # User enters code in their own browser
    $tenantId = az account show --query tenantId -o tsv
}

function Get-PBIToken {
    az account get-access-token `
        --resource https://analysis.windows.net/powerbi/api `
        --tenant $tenantId --query accessToken -o tsv
}
$token = Get-PBIToken
Write-Host "Power BI token obtained: $($token.Length) chars"
```

---

## PHASE 3 — Create Power BI workspace

```powershell
$token = Get-PBIToken
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }

$body = @{ name = "TableTalk Demo" } | ConvertTo-Json
$ws = Invoke-RestMethod -Method POST -Uri "https://api.powerbi.com/v1.0/myorg/groups" -Headers $headers -Body $body
$workspaceId = $ws.id
Write-Host "Workspace ID: $workspaceId"
$workspaceId | Set-Content "$workDir\workspace_id.txt"
```

---

## PHASE 4 — Create Contoso Retail push dataset

Write a complete Python script to `$workDir\build_dataset.py` and run it. The script must:
1. Create the dataset schema via POST `/datasets`
2. Generate 500 rows per table with the business story encoded
3. Push rows via POST `/datasets/{id}/tables/{name}/rows` (max 10,000 rows per call)
4. Save the dataset ID to `$workDir\dataset_id.txt`

### Business story (encode in data, NOT in agent instructions)
Contoso Retail Group, omnichannel (In-Store / Online / Mobile), 5 US regions, 2023–2025.
- West region: 25-30% lower conversion rate, higher returns
- Electronics: thin margin (15-20%). Beauty: fat margin (55-65%)
- Apparel: 22-28% return rate. Beauty: <3%
- Email CTR declining 3.5%→1.2% (2023–2025). Social ROI improving 1.8x→4.2x
- VIP customers (20%) drive ~65% of revenue
- 2 suppliers (S-003, S-007) with ~40% late delivery rate
- Sports & Outdoors: highest stockout rate (~20%)

### 13 tables (500 rows each):
dim_customers, dim_products, dim_stores, dim_employees, fact_orders, fact_order_items, fact_returns, fact_inventory, fact_marketing_campaigns, fact_website_sessions, fact_support_tickets, fact_supplier_performance, fact_store_traffic

### Run script:
```powershell
$token = Get-PBIToken
python "$workDir\build_dataset.py" $token $workspaceId
$datasetId = Get-Content "$workDir\dataset_id.txt"
Write-Host "Dataset ID: $datasetId"

# Validate
$query = @{ queries = @(@{ query = "EVALUATE ROW(`"n`", COUNTROWS(dim_customers))" }) } | ConvertTo-Json -Depth 5
$r = Invoke-RestMethod -Method POST -Uri "https://api.powerbi.com/v1.0/myorg/groups/$workspaceId/datasets/$datasetId/executeQueries" -Headers $headers -Body $query
Write-Host "Validation: $($r.results[0].tables[0].rows)"
# Should return 500
```

---

## PHASE 5 — Update agent and publish

### Clone agent locally
```powershell
# Get bot GUID
$botLine = (& $pac copilot list | Select-String "TableTalk with Fabric")
$botId = ($botLine -split '\s+')[1]  # second column is the GUID

& $pac copilot clone --bot $botId --output-dir "$workDir\agent"
```

### Update agent.mcs.yml — table names ONLY in the # Fabric # block

**CRITICAL BEST PRACTICE:** Put only table names in the `# Fabric #` block. Column discovery happens dynamically via `EVALUATE TOPN(3, tablename)` — do NOT add column lists. Do NOT add a DATA NARRATIVE section. Let the agent discover findings from live data.

```powershell
$agentPath = "$workDir\agent\TableTalk with Fabric\agent.mcs.yml"
$content = Get-Content $agentPath -Raw

# Find and update the Fabric block — replace workspace and dataset IDs
# Use .Replace() not -replace (safer with special chars)
$oldWsPattern = "workspaceid [a-f0-9-]{36}"
$oldDsPattern = "datasetid [a-f0-9-]{36}"
$content = [regex]::Replace($content, "workspaceid [a-f0-9-]{36}", "workspaceid $workspaceId")
$content = [regex]::Replace($content, "datasetid [a-f0-9-]{36}", "datasetid $datasetId")

# Update table list to just names (no column definitions)
# Find the existing tables: section and replace
$tableNames = "dim_customers, dim_products, dim_stores, dim_employees, fact_orders, fact_order_items, fact_returns, fact_inventory, fact_marketing_campaigns, fact_website_sessions, fact_support_tickets, fact_supplier_performance, fact_store_traffic"

# Replace tables section with clean table names only
$content = [regex]::Replace($content, "(?s)tables:.*?(?=\n\s*-\s*When|\n\s*\*\*URL|\nIf available)", "tables: $tableNames`n     ")

[System.IO.File]::WriteAllText($agentPath, $content, [System.Text.Encoding]::UTF8)
Write-Host "agent.mcs.yml updated"
```

### Verify connectionreferences.mcs.yml exists
```powershell
$connRefPath = "$workDir\agent\TableTalk with Fabric\connectionreferences.mcs.yml"
if (-not (Test-Path $connRefPath)) {
    # Create it — needed for PA flow connection
    @"
connectionReferences:
  - connectionReferenceLogicalName: new_sharedpowerbi_ff7fa
    connectorId: /providers/Microsoft.PowerApps/apis/shared_powerbi
"@ | Set-Content $connRefPath -Encoding UTF8
    Write-Host "connectionreferences.mcs.yml created"
}
```

### Verify Classic Generative Orchestration (MANDATORY)
```powershell
$settingsPath = "$workDir\agent\TableTalk with Fabric\settings.mcs.yml"
$settings = Get-Content $settingsPath -Raw
if ($settings -notmatch "GenerativeAIRecognizer") {
    Write-Host "WARNING: settings.mcs.yml does not have GenerativeAIRecognizer — fixing"
    $settings = $settings -replace "kind: CLIAgentRecognizer|kind: CLICopilotRecognizer", "kind: GenerativeAIRecognizer"
    Set-Content $settingsPath -Value $settings
}
Write-Host "Orchestrator verified: Classic Generative"
```

### Push and publish
```powershell
& $pac copilot push --project-dir "$workDir\agent\TableTalk with Fabric"
# Expect: "Push complete. N change(s) pushed."

& $pac copilot publish --bot $botId
# Expect: "Published successfully! ... Succeeded"
```

---

## PHASE 6 — Test the agent

Open the agent's test panel URL and run a short test battery. Use CDP browser automation or navigate manually.

**Before testing:** The first query will show a Power BI OAuth consent card. Click **Allow** once. This is expected.

**Test URL:**
`https://copilotstudio.microsoft.com/environments/{envId}/bots/{botId}/overview`
→ Click "Test your agent" → open test panel → start new conversation.

### 20 test questions (send 2-3 at a time, not all at once):

1. What tables and data do you have access to?
2. Which customer segment drives the most revenue?
3. Compare marketing channel ROI over time — which is best and worst?
4. Which product categories have the highest profit margins?
5. Which product categories have the highest return rates?
6. How does the West region compare to others in revenue and conversion?
7. Which suppliers have reliability issues?
8. What's the trend in email marketing CTR over the past 3 years?
9. Are there stockout risks? Which categories are worst affected?
10. Do support ticket volumes spike after major marketing campaigns?
11. What is the customer lifetime value by segment?
12. Which stores are underperforming on conversion rate?
13. What is the average order value by customer segment?
14. Compare social vs email campaigns ROI month by month.
15. What is revenue split by channel (In-Store vs Online vs Mobile)?
16. Which day of the week has the highest store traffic conversion?
17. Are VIP customers more or less likely to return products?
18. What inventory items are at immediate stockout risk?
19. Which campaigns generated the highest revenue lift?
20. Give me a comprehensive executive summary of the business with your top 3 recommendations.

### Expected timing per question: 60–180 seconds (this is normal — the agent writes real DAX queries and self-corrects)

Take a screenshot after question 20 completes. Save to `$workDir\test_screenshots\q20.png`.

---

## PHASE 7 — Quality analysis

Evaluate the test run:

| Dimension | What to check | Score (1-5) |
|---|---|---|
| Schema discovery | Correctly identified all 13 tables | |
| DAX correctness | Self-corrected on errors | |
| Specific numbers | Exact figures, not vague summaries | |
| Cross-metric reasoning | Connected findings across tables | |
| Strategic synthesis | Top 3 recommendations grounded in data | |
| Response depth | Analyst-level insight, not surface-level | |
| Error rate | Questions that returned errors or no data | |

Write findings to `$workDir\test_report.md`.

---

## PHASE 8 — Summary and user guide

After all phases complete, provide:

1. **Summary of what was done** — workspace ID, dataset ID, bot ID, tables created, questions tested, score
2. **The 20 test questions** (see Phase 6)
3. **Screenshot** of question 20 response

### How to use the agent

Open: [Copilot Studio](https://copilotstudio.microsoft.com) → your environment → **TableTalk with Fabric** → Test panel or Teams.

**First run:** Click **Allow** once for the Power BI connection.

**Just ask in plain English:**
- *"Which region has the lowest profit margin?"*
- *"Are our email campaigns still working?"*
- *"What's driving our return rate up?"*
- *"Give me 3 things I should fix this quarter"*

**Tips:**
- Ask complex multi-part questions — the agent breaks them down automatically
- Follow-up in the same session — it remembers context
- Ask for charts: "show me this as a bar chart"
- Expect 1–3 minutes per complex question — it's writing real DAX queries

**What it can't do:** Edit data, write back to Power BI, access data outside the connected dataset, return raw tables larger than 30K characters.

---

## Known pitfalls

| Gotcha | Fix |
|---|---|
| Playwright browser ≠ user's browser | Always use `az login --use-device-code` — never Playwright for auth |
| `.pbix` upload fails | Use push dataset API (Phase 4) — works on Power BI Pro, no Premium needed |
| `pac copilot publish` "not found" | Use bot GUID from `pac copilot list`, not schema name |
| `pac` not in PATH | Full path: `$env:USERPROFILE\.nuget\packages\microsoft.powerapps.cli\<ver>\tools\pac.exe` |
| PowerShell `-replace` breaks on special chars | Use `.Replace()` for literal strings |
| New Copilot Studio UI shows new orchestrator | Must use `recognizer: kind: GenerativeAIRecognizer` in settings.mcs.yml |
| First-time OAuth consent card blocks first query | Click Allow — expected on first use |
| `pac copilot push` "no changes detected" | Do `pac copilot pull` first to sync, then edit, then push |
| connectionreferences.mcs.yml missing | Create it manually (see Phase 5) — without it PA flows silently fail |
| Agent puts full column lists in instructions | Table names ONLY in # Fabric # block — TOPN(3) handles column discovery |


