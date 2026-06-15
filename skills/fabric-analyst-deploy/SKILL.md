---
name: "fabric-analyst-deploy"
description: "End-to-end deployment skill for the Fabric Analyst agent (New Generative Orchestrator). Deploys agent via PAC CLI + Dataverse API. Generates ContosoRetail push dataset (13 tables), configures agent instructions, adds Power BI tools via CDP browser automation, adds full schema and DAX pattern skills via Dataverse API, publishes, and tests. Skips phases that already exist. See /copilot-studio-new-orchestrator for architecture reference."
---

# Fabric Analyst — Full Deployment Skill (NGO)

Deploy the **Fabric Analyst** agent (New Generative Orchestrator architecture) into any Power Platform environment with Copilot Studio. Fully autonomous after 4 upfront questions.

**What is automated:** Agent shell creation (PAC CLI + Dataverse API), dataset generation, agent configuration and instructions (Dataverse API), Copilot Studio agent skills with full ContosoRetail schema (Dataverse API), publishing.

**What requires a CDP browser session:** Adding connector Tools (Power BI) — Copilot Studio does not expose a CLI or API for this step. The skill sets up a dedicated Edge profile for CDP and automates the UI interaction. On first use you sign in once; subsequent runs reuse the profile.

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

The dataset generator is included in this repo at `dataset/build_contoso_dataset.py`.

```powershell
# Copy it to your working directory
Copy-Item "$repoRoot\dataset\build_contoso_dataset.py" "$workDir\build_dataset.py"

# Install dependencies (once)
pip install faker requests

# Run — uses your Az CLI token automatically
python "$workDir\build_dataset.py" $workspaceId $tenantId
# Outputs: $workDir\dataset_id.txt
$datasetId = Get-Content "$workDir\dataset_id.txt"
Write-Host "Dataset ID: $datasetId"
```

Where `$repoRoot` is the root of your cloned `nl2query-agent-labs` repo. If you haven't cloned it:
```powershell
git clone https://github.com/KarimaKT/nl2query-agent-labs "$workDir\repo"
$repoRoot = "$workDir\repo"
```

The script creates all 13 ContosoRetail tables (dim_customers, dim_products, dim_stores, dim_employees, fact_orders, fact_order_items, fact_returns, fact_inventory, fact_marketing_campaigns, fact_website_sessions, fact_support_tickets, fact_supplier_performance, fact_store_traffic) with 500 rows each, deterministic (seed=42).

If you already have a Power BI dataset to use, skip Phase 2 and set `$workspaceId` and `$datasetId` directly.

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
    "6. After any multi-metric analysis, offer to generate a file: an HTML report with Chart.js charts (includes executive summary, charts per metric, data tables, follow-up questions) or a PPT presentation (title + summary slide, one slide per metric, recommendations slide). Every report delivery uses a new timestamped filename (e.g. ContosoAnalysis-YYYYMMDD-HHMMSS.html). When updating an existing report (adding new data or applying user-requested changes), carry over the prior content, apply the update, and always re-deliver as a new file so the user gets a fresh download link. " +
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
Use `.preview.` for preview environments, omit `.preview.` for production.

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

# Build schema skill content
$schemaContent = @"
## ContosoRetail Schema

Dataset type: Power BI push dataset. NO active relationships between tables.
For ALL cross-table joins use SUMX(FILTER()) pattern — RELATED() and USERELATIONSHIP() do not work.

WorkspaceID and DatasetID are in your instructions.

## Dimension Tables

### dim_customers
- customer_id (string, PK) — e.g. "CUST0001"
- customer_name (string)
- customer_segment (string) — values: "New", "Regular", "VIP", "At-Risk"
- email (string)
- region (string) — values: "Northeast", "Southeast", "Midwest", "Southwest", "West"
- signup_date (datetime)
- lifetime_value (decimal)

### dim_products
- product_id (string, PK) — e.g. "PROD001"
- product_name (string)
- category (string) — values: "Electronics", "Beauty", "Apparel", "Sports & Outdoors", "Home & Garden"
- unit_cost (decimal)
- unit_price (decimal)
- margin_pct (decimal) — gross margin as decimal (e.g. 0.598 = 59.8%)

### dim_stores
- store_id (string, PK) — e.g. "ST01"
- store_name (string)
- region (string) — same values as dim_customers region
- store_type (string) — "Flagship", "Standard", "Outlet"
- manager_name (string)

### dim_employees
- employee_id (string, PK)
- employee_name (string)
- department (string)
- store_id (string, FK → dim_stores)
- performance_rating (decimal 1-5)
- quota_attainment (decimal) — NOTE: may not always be populated

## Fact Tables

### fact_orders
- order_id (string, PK) — e.g. "O0001"
- customer_id (string, FK → dim_customers)
- store_id (string, FK → dim_stores)
- order_date (datetime)
- order_value (decimal) — total order value
- channel (string) — "In-Store", "Online", "Mobile App"
- region (string)

### fact_order_items
- order_item_id (string, PK)
- order_id (string, FK → fact_orders)
- product_id (string, FK → dim_products)
- quantity (integer)
- unit_price (decimal)
- discount_pct (decimal)

### fact_returns
- return_id (string, PK)
- order_item_id (string, FK → fact_order_items)
- return_date (datetime)
- return_reason (string)
- customer_id (string, FK → dim_customers)
- product_id (string, FK → dim_products)

### fact_inventory
- inventory_id (string, PK)
- store_id (string, FK → dim_stores)
- product_id (string, FK → dim_products)
- stock_level (integer)
- reorder_point (integer)
- stockout_flag (string) — "Yes" or "No"
- last_restocked (datetime)

### fact_marketing_campaigns
- campaign_id (string, PK)
- campaign_name (string)
- channel (string) — "Email", "Social", "Display"
- start_date (datetime)
- end_date (datetime)
- campaign_cost (decimal)
- revenue_lift (decimal)
- net_revenue_lift (decimal)
- roi (decimal) — net_revenue_lift / campaign_cost

### fact_website_sessions
- session_id (string, PK)
- customer_id (string, FK → dim_customers)
- session_date (datetime)
- pages_viewed (integer)
- conversion_flag (string) — "Yes" or "No"
- channel (string)

### fact_support_tickets
- ticket_id (string, PK)
- customer_id (string, FK → dim_customers)
- open_date (datetime)
- close_date (datetime)
- issue_category (string)
- resolved_flag (string) — "Yes" or "No"
- campaign_id (string, FK → fact_marketing_campaigns, nullable)

### fact_supplier_performance
- supplier_id (string, PK) — e.g. "SUP01"
- supplier_name (string)
- product_id (string, FK → dim_products)
- on_time_flag (string) — "Yes" or "No"
- quality_score (decimal 0-10)
- po_value (decimal)

### fact_store_traffic
- traffic_id (string, PK)
- store_id (string, FK → dim_stores)
- traffic_date (datetime)
- visitor_count (integer)
- conversion_rate (decimal)
- day_of_week (string)

## Join Patterns (no active relationships — always use SUMX/FILTER)

Revenue by customer segment:
SUMX(FILTER(fact_orders, fact_orders[customer_id] = dim_customers[customer_id]), fact_orders[order_value])

Product category margin:
AVERAGEX(FILTER(dim_products, dim_products[category] = "Beauty"), dim_products[margin_pct])

Return rate by category:
DIVIDE(
  COUNTROWS(FILTER(fact_returns, CALCULATE(VALUES(dim_products[category])) = "Electronics")),
  COUNTROWS(fact_order_items)
)

Supplier on-time rate:
DIVIDE(
  COUNTROWS(FILTER(fact_supplier_performance, fact_supplier_performance[on_time_flag] = "Yes")),
  COUNTROWS(fact_supplier_performance)
)

Store traffic conversion:
AVERAGEX(FILTER(fact_store_traffic, fact_store_traffic[store_id] = dim_stores[store_id]), fact_store_traffic[conversion_rate])
"@

# Build DAX patterns skill content
$daxContent = @"
## DAX Patterns for ContosoRetail NL2Query

All patterns assume NO active relationships. Use SUMX(FILTER()) for every cross-table calculation.

## Schema exploration (always run first on unfamiliar table)
EVALUATE TOPN(3, dim_customers)
EVALUATE TOPN(3, fact_orders)

## Revenue aggregations

Revenue by customer segment:
SUMMARIZECOLUMNS(
  dim_customers[customer_segment],
  "Revenue", SUMX(FILTER(fact_orders, fact_orders[customer_id] = dim_customers[customer_id]), fact_orders[order_value]),
  "Order_Count", COUNTROWS(FILTER(fact_orders, fact_orders[customer_id] = dim_customers[customer_id]))
)

Revenue by region:
SUMMARIZECOLUMNS(
  fact_orders[region],
  "Revenue", SUM(fact_orders[order_value]),
  "Orders", COUNTROWS(fact_orders)
)

Revenue by channel:
SUMMARIZECOLUMNS(
  fact_orders[channel],
  "Revenue", SUM(fact_orders[order_value])
)

## Product and category analysis

Category margin:
SUMMARIZECOLUMNS(
  dim_products[category],
  "Avg_Margin_Pct", AVERAGEX(dim_products, dim_products[margin_pct]),
  "Product_Count", COUNTROWS(dim_products)
)

Return rate by category (cross-table):
SUMMARIZECOLUMNS(
  dim_products[category],
  "Return_Count", COUNTROWS(FILTER(fact_returns, CALCULATE(COUNTROWS(FILTER(dim_products, dim_products[product_id] = fact_returns[product_id]))) > 0)),
  "Item_Count", COUNTROWS(FILTER(fact_order_items, CALCULATE(COUNTROWS(FILTER(dim_products, dim_products[product_id] = fact_order_items[product_id]))) > 0))
)

## Marketing analysis

Campaign ROI by channel and year:
SUMMARIZECOLUMNS(
  fact_marketing_campaigns[channel],
  "Total_Cost", SUM(fact_marketing_campaigns[campaign_cost]),
  "Net_Lift", SUM(fact_marketing_campaigns[net_revenue_lift]),
  "Avg_ROI", AVERAGE(fact_marketing_campaigns[roi])
)

## Supplier reliability

Supplier on-time delivery rate:
SUMMARIZECOLUMNS(
  fact_supplier_performance[supplier_id],
  "On_Time_Rate", DIVIDE(COUNTROWS(FILTER(fact_supplier_performance, fact_supplier_performance[on_time_flag] = "Yes")), COUNTROWS(fact_supplier_performance)),
  "Avg_Quality", AVERAGE(fact_supplier_performance[quality_score]),
  "PO_Value", SUM(fact_supplier_performance[po_value])
)

## Inventory and stockout

Stockout rate by category (cross-table):
SUMMARIZECOLUMNS(
  dim_products[category],
  "Stockout_Count", COUNTROWS(FILTER(fact_inventory, fact_inventory[stockout_flag] = "Yes" && CALCULATE(COUNTROWS(FILTER(dim_products, dim_products[product_id] = EARLIER(fact_inventory[product_id])))) > 0)),
  "Total_Count", COUNTROWS(fact_inventory)
)

## Customer lifetime value

LTV by segment:
SUMMARIZECOLUMNS(
  dim_customers[customer_segment],
  "Avg_LTV", AVERAGEX(dim_customers, dim_customers[lifetime_value]),
  "Customer_Count", COUNTROWS(dim_customers),
  "Total_LTV", SUMX(dim_customers, dim_customers[lifetime_value])
)

## Self-correction patterns

If a query returns all equal values across groups, the join is likely wrong.
Try: SUMX(FILTER(fact_table, fact_table[fk_col] = EARLIER(dim_table[pk_col])), fact_table[measure])
instead of: CALCULATE(SUM(fact_table[measure]), FILTER(...))

If TOPN returns columns you don't expect, note the actual column names before aggregating.
"@

Add-AgentSkill "schema-definitions" "ContosoRetail dataset schema — all 13 tables, column types, and join patterns" $schemaContent
Add-AgentSkill "dax-patterns" "DAX patterns for ContosoRetail — revenue, categories, marketing ROI, supplier reliability, LTV" $daxContent
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
| New orchestration experience required | NGO requires the new Copilot Studio experience — available in most regions as of mid-2026 |
| ALL agents show InvalidContent error | Platform outage (not your YAML) — check a known-working agent, wait 1-4 hours |
| Anthropic models not available | Requires Anthropic license in tenant — contact admin if Claude series not in model picker |






