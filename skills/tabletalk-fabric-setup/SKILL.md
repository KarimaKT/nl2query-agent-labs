---
name: "tabletalk-fabric-setup"
description: "End-to-end setup skill for TableTalk with Fabric: install Copilot Studio solution, create Power BI push dataset, upload sample data, update agent instructions, push and publish. Based on proven steps from C:\\src\\Fabric CDX tenant setup."
---


# TableTalk with Fabric — End-to-End Setup Skill

This skill captures every proven step for deploying the TableTalk with Fabric Copilot Studio solution into a Power Platform environment. Use this to avoid reinventing the wheel.

---

## Prerequisites checklist
- PAC CLI installed: `dotnet tool install --global Microsoft.PowerApps.CLI.Tool`
  - Binary ends up at: `C:\Users\<user>\.nuget\packages\microsoft.powerapps.cli\<version>\tools\pac.exe`
- Az CLI installed: `winget install Microsoft.AzureCLI`
- Python 3 available (for fallback REST uploads)
- GitHub access to `https://github.com/NicoPilot-dev/TableTalkWithFabric`

---

## Step 1 — Clone the repo
```powershell
cd C:\src
git clone https://github.com/NicoPilot-dev/TableTalkWithFabric Fabric
```
Solution zip is at: `C:\src\Fabric\TableTalkFabric_1_0_0_1.zip`

---

## Step 2 — Authenticate PAC CLI to target environment
```powershell
$pac = "C:\Users\$env:USERNAME\.nuget\packages\microsoft.powerapps.cli\2.8.1\tools\pac.exe"
& $pac auth create --environment https://org<id>.crm.dynamics.com --name CDX
# Follow device code prompt — paste code at https://microsoft.com/devicelogin
```

---

## Step 3 — Import the solution
```powershell
& $pac solution import --path "C:\src\Fabric\TableTalkFabric_1_0_0_1.zip" --environment <envId>
```
Solution ID after import: check `pac solution list --environment <envId>`

---

## Step 4 — Auth via Az CLI (CRITICAL — use device code, NOT browser)
```powershell
az login --tenant <tenantId> --use-device-code
# User pastes device code in their own signed-in browser
az account get-access-token --resource https://analysis.windows.net/powerbi/api --tenant <tenantId> --query accessToken -o tsv
```
- ⚠️ Do NOT attempt browser-based auth via Playwright for Power BI — use az CLI device code every time
- Token resource for Power BI REST: `https://analysis.windows.net/powerbi/api`
- Token resource for Power Platform flows: `https://service.flow.microsoft.com/`
- Token resource for Power Apps connections: `https://service.powerapps.com/`

---

## Step 5 — Create Power BI workspace
```powershell
$token = az account get-access-token --resource https://analysis.windows.net/powerbi/api --tenant <tenantId> --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
$body = @{ name = "TableTalk Demo" } | ConvertTo-Json
$resp = Invoke-RestMethod -Method POST -Uri "https://api.powerbi.com/v1.0/myorg/groups" -Headers $headers -Body $body
$workspaceId = $resp.id
Write-Host "Workspace ID: $workspaceId"
```

---

## Step 6 — Create push dataset (NOT .pbix upload)
**⚠️ CRITICAL LESSON: Do NOT try to upload .pbix via REST API.**
- The `go.microsoft.com/fwlink/?LinkID=521962` link downloads an **xlsx**, not a pbix
- Power BI REST API `/imports` endpoint rejects xlsx with `RequestedFileIsEncryptedOrCorrupted`
- Power BI REST API `/imports` only accepts real .pbix files
- **Use push datasets instead — works on Power BI Pro, no Premium needed**

```powershell
$token = az account get-access-token --resource https://analysis.windows.net/powerbi/api --tenant <tenantId> --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
$groupId = "<workspaceId>"

$dataset = @{
    name = "FinancialSample"
    tables = @(
        @{
            name = "financials"
            columns = @(
                @{ name = "Segment"; dataType = "string" }
                @{ name = "Country"; dataType = "string" }
                @{ name = "Product"; dataType = "string" }
                @{ name = "DiscountBand"; dataType = "string" }
                @{ name = "UnitsSold"; dataType = "double" }
                @{ name = "ManufacturingPrice"; dataType = "double" }
                @{ name = "SalePrice"; dataType = "double" }
                @{ name = "GrossSales"; dataType = "double" }
                @{ name = "Discounts"; dataType = "double" }
                @{ name = "Sales"; dataType = "double" }
                @{ name = "COGS"; dataType = "double" }
                @{ name = "Profit"; dataType = "double" }
                @{ name = "Date"; dataType = "datetime" }
                @{ name = "MonthNumber"; dataType = "int64" }
                @{ name = "MonthName"; dataType = "string" }
                @{ name = "Year"; dataType = "int64" }
            )
        }
    )
} | ConvertTo-Json -Depth 10

$resp = Invoke-RestMethod -Method POST -Uri "https://api.powerbi.com/v1.0/myorg/groups/$groupId/datasets" -Headers $headers -Body $dataset
$datasetId = $resp.id
Write-Host "Dataset ID: $datasetId"
```

---

## Step 7 — Push sample rows
```powershell
$rows = @{ rows = @(
    @{ Segment="Government"; Country="Canada"; Product="Carretera"; DiscountBand="None"; UnitsSold=1618.5; ManufacturingPrice=3; SalePrice=20; GrossSales=32370; Discounts=0; Sales=32370; COGS=16185; Profit=16185; Date="2014-01-01"; MonthNumber=1; MonthName="January"; Year=2014 }
    @{ Segment="Government"; Country="Germany"; Product="Carretera"; DiscountBand="None"; UnitsSold=1321; ManufacturingPrice=3; SalePrice=20; GrossSales=26420; Discounts=0; Sales=26420; COGS=13210; Profit=13210; Date="2014-01-01"; MonthNumber=1; MonthName="January"; Year=2014 }
    @{ Segment="Midmarket"; Country="France"; Product="Carretera"; DiscountBand="None"; UnitsSold=2178; ManufacturingPrice=3; SalePrice=15; GrossSales=32670; Discounts=0; Sales=32670; COGS=21780; Profit=10890; Date="2014-01-01"; MonthNumber=1; MonthName="January"; Year=2014 }
    @{ Segment="Government"; Country="Canada"; Product="Montana"; DiscountBand="None"; UnitsSold=2310.5; ManufacturingPrice=5; SalePrice=20; GrossSales=46210; Discounts=0; Sales=46210; COGS=23105; Profit=23105; Date="2014-02-01"; MonthNumber=2; MonthName="February"; Year=2014 }
    @{ Segment="Government"; Country="United States of America"; Product="Paseo"; DiscountBand="Medium"; UnitsSold=1819; ManufacturingPrice=10; SalePrice=33; GrossSales=60027; Discounts=6002.7; Sales=54024.3; COGS=18190; Profit=35834.3; Date="2014-03-01"; MonthNumber=3; MonthName="March"; Year=2014 }
    @{ Segment="Enterprise"; Country="France"; Product="Velo"; DiscountBand="None"; UnitsSold=1479; ManufacturingPrice=120; SalePrice=125; GrossSales=184875; Discounts=0; Sales=184875; COGS=177480; Profit=7395; Date="2014-04-01"; MonthNumber=4; MonthName="April"; Year=2014 }
    @{ Segment="Government"; Country="Germany"; Product="VTT"; DiscountBand="Medium"; UnitsSold=2821; ManufacturingPrice=250; SalePrice=350; GrossSales=987350; Discounts=98735; Sales=888615; COGS=705250; Profit=183365; Date="2014-05-01"; MonthNumber=5; MonthName="May"; Year=2014 }
    @{ Segment="Channel Partners"; Country="United States of America"; Product="Amarilla"; DiscountBand="High"; UnitsSold=2835; ManufacturingPrice=260; SalePrice=350; GrossSales=992250; Discounts=198450; Sales=793800; COGS=736100; Profit=57700; Date="2014-06-01"; MonthNumber=6; MonthName="June"; Year=2014 }
) } | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method POST -Uri "https://api.powerbi.com/v1.0/myorg/groups/$groupId/datasets/$datasetId/tables/financials/rows" -Headers $headers -Body $rows
```

---

## Step 8 — Validate DAX executeQueries works
```powershell
$query = @{ queries = @(@{ query = "EVALUATE TOPN(3, financials, [Sales], DESC)" }) } | ConvertTo-Json -Depth 5
$result = Invoke-RestMethod -Method POST -Uri "https://api.powerbi.com/v1.0/myorg/groups/$groupId/datasets/$datasetId/executeQueries" -Headers $headers -Body $query
$result.results[0].tables[0].rows | ConvertTo-Json -Depth 3
# Should return top 3 rows by Sales — if this works, the agent flows will work too
```

---

## Step 9 — Clone agent locally
```powershell
$pac = "C:\Users\$env:USERNAME\.nuget\packages\microsoft.powerapps.cli\2.8.1\tools\pac.exe"
& $pac copilot clone --environment <envId> --bot "TableTalk with Fabric" --output-dir "C:\src\Fabric\agent"
```

---

## Step 10 — Update agent.mcs.yml
File: `C:\src\Fabric\agent\TableTalk with Fabric\agent.mcs.yml`

Replace in the `# Fabric #` block:
- Old `workspaceid b644fcd3-...` → new workspace ID
- Old `datasetid 8a6a855e-...` → new dataset ID
- Old `tables : bot, conversationtranscript` → `tables : financials (columns: Segment, Country, ...)`
- Remove the Power BI report URL line referencing Nico Sprotti's tenant

```powershell
$agentPath = "C:\src\Fabric\agent\TableTalk with Fabric\agent.mcs.yml"
$content = Get-Content $agentPath -Raw
$content = $content.Replace('<old-workspace-id>', '<new-workspace-id>')
$content = $content.Replace('<old-dataset-id>', '<new-dataset-id>')
$content = $content.Replace('Copilot log activities:', 'Financial Sample dataset:')
$content = $content.Replace('tables : bot, conversationtranscript.', 'tables : financials (columns: Segment, Country, Product, DiscountBand, UnitsSold, ManufacturingPrice, SalePrice, GrossSales, Discounts, Sales, COGS, Profit, Date, MonthNumber, MonthName, Year).')
$content = $content -replace '\r?\n     - When appropriate offer links.*?renders correctly\.', ''
[System.IO.File]::WriteAllText($agentPath, $content, [System.Text.Encoding]::UTF8)
```

---

## Step 11 — Verify Classic Generative Orchestration
Check `C:\src\Fabric\agent\TableTalk with Fabric\settings.mcs.yml`:
```yaml
recognizer:
  kind: GenerativeAIRecognizer
```
This = Classic generative orchestration. If it says `MultiIntentRecognizer` or `OrchestratorRecognizer`, change it to `GenerativeAIRecognizer`.

---

## Step 12 — Push agent back
```powershell
$pac = "C:\Users\$env:USERNAME\.nuget\packages\microsoft.powerapps.cli\2.8.1\tools\pac.exe"
& $pac copilot push --project-dir "C:\src\Fabric\agent\TableTalk with Fabric" --environment <envId>
```

---

## Step 13 — Publish agent
```powershell
# First get the bot ID
& $pac copilot list --environment <envId>
# Find "TableTalk with Fabric" row and copy the Copilot ID

& $pac copilot publish --environment <envId> --bot "<copilot-id>"
# Expected: "Published successfully! <id> Succeeded"
```

---

## Step 14 — Verify flows are running
```powershell
$flowToken = az account get-access-token --resource https://service.flow.microsoft.com/ --tenant <tenantId> --query accessToken -o tsv
$flowHeaders = @{ Authorization = "Bearer $flowToken" }
$flows = Invoke-RestMethod -Uri "https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple/environments/<envId>/flows?api-version=2016-11-01" -Headers $flowHeaders
$flows.value | Where-Object { $_.properties.displayName -like "*TableTalk*" } | Select-Object @{n="Name";e={$_.properties.displayName}}, @{n="State";e={$_.properties.state}}
# Both should show State = "Started"
```

---

## Known IDs (Karima's CDX setup)
| Resource | ID |
|---|---|
| CDX Environment ID | `61453fde-f312-e19f-b879-a2dfa518e914` |
| CDX Tenant ID | `301759bc-5be1-40f1-8a44-822e286f5a9d` |
| CDX Account | `karima@M365x05526665.onmicrosoft.com` |
| TableTalk Bot ID | `3a1ef82e-a93a-4bf7-bf9a-dbfebc8fc421` |
| TableTalk Demo Workspace ID | `f9b7b05b-44c8-4740-9372-b9a958007c63` |
| FinancialSample Dataset ID | `cb908b7c-5428-4c4b-85b1-8f59d2131d24` |

---

## Common pitfalls
1. **Browser auth won't work** — Playwright uses `mcp-msedge` profile, separate from user's real browser. Always use `az login --use-device-code` for token acquisition.
2. **PowerShell heredoc with special chars** — Single quotes in `-replace` patterns break. Use `.Replace()` string method instead of `-replace` for literal strings.
3. **.pbix upload via REST is tricky** — `System.Net.Http.ByteArrayContent` needs `[System.Net.Http.ByteArrayContent]::new($bytes, 0, $bytes.Length)` syntax; PowerShell `-InFile` is wrong for multipart.
4. **Push dataset vs .pbix** — Use push datasets (Step 6) for Pro tenants. Premium/Fabric not needed.
5. **pac copilot publish requires `--bot <ID>`** — Not schema name, not display name. Use `pac copilot list` to get the GUID.
6. **`pac` not in PATH** — Full path: `C:\Users\<user>\.nuget\packages\microsoft.powerapps.cli\<version>\tools\pac.exe`

