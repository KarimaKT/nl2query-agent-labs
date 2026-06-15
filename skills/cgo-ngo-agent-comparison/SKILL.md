---
name: "cgo-ngo-agent-comparison"
description: "Generic skill to compare any two Copilot Studio agents (CGO and/or NGO). Explores agent config and data sources to generate grounded Q+A pairs. Tests information retrieval, task completion, and goal-based behavior. Organized by purpose buckets (not tool count). Applies multiple graders per test. Produces qualitative narrative report with scores as analysis aids, plus self-correction instructions and skill addendums for the next run."
---

# Generic Agent Comparison Skill (CGO / NGO)

## README — What This Skill Does and Why

This skill runs a structured, adaptive comparison between any two Copilot Studio agents. It:
1. Explores each agent's actual configuration and samples its data/knowledge sources
2. Generates grounded test questions with inferred expected answers
3. Runs tests organized by purpose bucket (not tool count)
4. Applies multiple graders per test
5. Produces a qualitative narrative report with scores as analysis aids
6. Outputs self-correction instructions and skill addendums for the next run
7. Generates CGO-ready in-product evaluation CSV files

This skill works for **information retrieval agents**, **task completion agents**, and anything in between.

### CGO and NGO — what the acronyms mean

**CGO — Classic Generative Orchestration**  
`recognizer: kind: GenerativeAIRecognizer`, `template: default-2.1.0`. Routes messages to topics; topics invoke PA flows. Conversation variables, Adaptive Card output, in-product Evaluation. Stable and production-ready.

**NGO — New Generative Orchestration**  
`recognizer.$kind: CLICopilotRecognizer`, `template: cliagent-1.0.0`. No topics — only Tools and Skills. Reasoning loop handles orchestration, parallel tool calls, self-correction natively. Inline reasoning visible in chat. No in-product Evaluation yet. Some features maturing (no conversation variables, no inline charts, PAC CLI push crashes on settings).

---

## STEP 0 — Ask these inputs upfront

```
1. Path or URL to Agent 1: [local folder OR Copilot Studio bot ID/URL]
2. Path or URL to Agent 2: [local folder OR bot ID/URL]
3. Environment ID: [GUID, or blank if local]
4. How many test questions? [default: 20, max: 100]
5. Mode: [auto] run through all steps, OR [2-step] pause for approval after question generation and after eval criteria
6. Agent domain / goals? [optional description of what the agent is supposed to do]
7. Known edge cases or guardrails? [optional]
8. Known accepted input values or field constraints? [optional — used to generate valid/invalid input tests]
9. Test set with known correct answers? [optional: path to CSV with question,expectedResponse]
10. Output folder: [default: working-dir\AgentComparison\<timestamp>]
```

If agent paths not provided, discover:
```powershell
$pac = (Get-ChildItem "$env:USERPROFILE\.nuget\packages\microsoft.powerapps.cli" -Recurse -Filter "pac.exe" | Select-Object -First 1).FullName
& $pac copilot list
& $pac copilot clone --bot <botId> --output-dir <tempDir>
```

---


---

## LEARNINGS.md — persistent session knowledge

The skill maintains a `LEARNINGS.md` file in the output folder. This preserves discovered IDs, question sets, divergences, and scoring calibrations across runs so you don't start from scratch each time.

### Load at start

```powershell
$learnFile = "$outputFolder\LEARNINGS.md"
if (Test-Path $learnFile) {
    $learnings = Get-Content $learnFile -Raw
    Write-Host "=== Loaded prior learnings ==="
    Write-Host $learnings
    # Extract known values — skip discovery phases if IDs are already known
    if ($learnings -match 'agent1BotId:\s*(\S+)') { $agent1BotId = $Matches[1] }
    if ($learnings -match 'agent2BotId:\s*(\S+)') { $agent2BotId = $Matches[1] }
    if ($learnings -match 'envId:\s*(\S+)') { $envId = $Matches[1] }
}
```

### Write at end

```powershell
$learnContent = @"
# Agent Comparison — Session Learnings
Last updated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')

## Agent IDs
- agent1BotId: $agent1BotId
- agent1Type: CGO or NGO
- agent2BotId: $agent2BotId
- agent2Type: CGO or NGO
- envId: $envId
- outputFolder: $outputFolder

## Question Set (last used)
<!-- Paste final question list here after generation — reuse on next run or extend -->

## Scoring calibrations
<!-- Note any scoring criteria that were revised mid-run so next run starts correctly calibrated -->

## Known divergences
<!-- Questions where agents gave materially different answers — flag for manual DAX verification -->

## Session notes
- $(Get-Date -Format 'yyyy-MM-dd'): <summary of findings>
"@
$learnContent | Set-Content $learnFile -Encoding UTF8
Write-Host "Learnings saved: $learnFile"
```

### Skill addendum pattern

If this run produces use-case-specific learnings (e.g. data shapes, grader calibrations, known-good answers), write a companion `SKILL-ADDENDUM.md` in the output folder:

```powershell
$addendumFile = "$outputFolder\SKILL-ADDENDUM.md"
@"
# Skill Addendum — <AgentName> Comparison
Generated: $(Get-Date -Format 'yyyy-MM-dd')

## Use-case specific context
<!-- What makes this agent/data unusual, things to check on every run -->

## Pre-validated answers
<!-- Questions and answers verified by manual DAX check or both agents agreeing -->

## Grader calibrations
<!-- Scoring criteria adjusted for this use case, with rationale -->

## Agent improvement recommendations
<!-- Specific improvements observed in this run, agent-by-agent -->
"@ | Set-Content $addendumFile -Encoding UTF8
```

On the next run, check for both `LEARNINGS.md` and `SKILL-ADDENDUM.md` and load them before generating questions or scoring.

---
## STEP 1 — Explore each agent's configuration

Read the cloned YAML files:
```powershell
$settings = Get-Content "$agentDir\settings.mcs.yml" -Raw
$type = if ($settings -match "CLICopilotRecognizer") { "NGO" }
        elseif ($settings -match "GenerativeAIRecognizer") { "CGO" } else { "Unknown" }
$agentYml = Get-Content "$agentDir\agent.mcs.yml" -Raw
$tools = Get-ChildItem "$agentDir\actions" -Filter "*.mcs.yml" -ErrorAction SilentlyContinue
$knowledge = Get-ChildItem "$agentDir\knowledge" -ErrorAction SilentlyContinue
$skills = Get-ChildItem "$agentDir\skills" -ErrorAction SilentlyContinue
$topics = Get-ChildItem "$agentDir\topics" -Filter "*.mcs.yml" -ErrorAction SilentlyContinue
```

For each tool/action: read `modelDisplayName`, `modelDescription`, input names and descriptions.
For each knowledge source: note type (SharePoint, file, website) and apparent content domain.
For each skill: read name and description.
For topics (CGO): note trigger phrases and what the topic does.

### Sample the agent's actual capabilities

Send minimal probes to each agent to understand what it can actually do:
- **"What can you help me with?"** → captures the agent's self-description
- **"What data/information do you have access to?"** → reveals scope
- For data-connected agents: send a schema exploration query

For each tool, also send a minimal triggering question and capture the raw output. This becomes the basis for generating expected answers.

### Sample the data source (if accessible)

For Power BI datasets:
```powershell
# Get table list and row counts
$token = az account get-access-token --resource https://analysis.windows.net/powerbi/api --query accessToken -o tsv
$q = '{"queries":[{"query":"EVALUATE SELECTCOLUMNS(INFO.COLUMNS(),\"Table\",[TableName],\"Column\",[Name])"}]}'
Invoke-RestMethod "https://api.powerbi.com/v1.0/myorg/groups/$wsId/datasets/$dsId/executeQueries" -Method POST -Headers @{Authorization="Bearer $token";"Content-Type"="application/json"} -Body $q
```

For Dataverse / SharePoint / document knowledge: note the accessible content areas, key entities, document titles.

Output an agent profile:
```
Agent: [name] | Type: CGO/NGO | Model: [model] | Orchestrator: [CGO/NGO]
Tools: [list with descriptions]
Knowledge: [list with content domains]
Skills: [list with descriptions]
Topics (CGO): [list]
Data scope: [what data is accessible]
Agent purpose (inferred): [information retrieval / task completion / both]
```

---

## STEP 2 — Generate grounded test questions with expected answers

### Design principle: ground before generating

Do NOT generate questions from imagination. Generate questions from what the agent actually has:
1. From tool descriptions: what does each tool claim to do? Generate questions that exercise it.
2. From data samples: what values actually exist in the data? Generate questions that reference real values.
3. From knowledge source content: what facts are in the documents? Generate questions whose answers are in the source.
4. From agent instructions: what does the agent explicitly say it can/cannot do? Generate both in-scope and out-of-scope questions.
5. From known accepted input values (if provided): generate valid-input and invalid-input variants.

### For each generated question, also generate:
- **expectedAnswer**: the correct answer, inferred from data/source sampling. Mark as `[inferred]` if generated from samples, `[verified]` if confirmed by querying the source, `[user-provided]` if given in the input test set.
- **gradingCriteria**: a specific, evaluable criterion per grader (not "answer is correct" but "answer must include the specific revenue figure for the At-Risk segment")
- **expectedToolOrBehavior**: which tool should fire, OR what behavior the agent should exhibit (e.g. "should refuse", "should ask clarifying question", "should complete task X")

### Purpose buckets

Organize tests by WHY you are running them, not by how many tools fire:

**Foundational Core** — The must-pass set. Essential quality at deployment. A fail means something broke. If running a regression: this set catches it.
- Covers the agent's core stated purpose
- Includes happy-path versions of the most important use cases
- Expected answers are verified or high-confidence

**Architecture** — Tests functional behavior of specific components. A fail points to a specific thing to debug.
- Knowledge retrieval: did it find the right fact in the right source?
- Tool invocation: did the right tool fire? (observed as a quality signal, not as a pass/fail criterion on its own)
- Routing (CGO): did it reach the right topic?
- Goal decomposition (NGO): did the reasoning loop plan correctly?
- Note: a complex goal-based question can still be an architecture test — the question is whether the components behaved correctly, not how many there were.

**Robustness** — Same question, different phrasings or added context. A fail means the agent is too brittle.
- Rephrase 3–5 core questions formally, casually, with typos, with irrelevant context
- The agent should answer consistently

**Edge Cases & Guardrails** — Boundary conditions and prohibited behaviors. A fail means guardrails need work.
- Out-of-scope questions (agent should refuse or clarify)
- Adversarial inputs (agent should not hallucinate)
- Invalid input values (agent should handle gracefully)
- Ambiguous questions (agent should ask for clarification, not guess)

**High-Value Goals** — The highest-complexity use cases. A fail means the agent cannot deliver its most valuable capability.
- Multi-step task completion with multiple tool calls
- Complex synthesis across multiple data sources or documents
- Multi-intent questions (agent must address 2–3 distinct requests in one response)
- Multi-turn goal completion (task requires several conversation turns)

**Task Completion** — If the agent can take actions (write files, send messages, create records, trigger workflows): tests that verify end-to-end task execution, partial failure recovery, and output verification.
- Task: initiate an action
- Verify: confirm the action completed (check the artifact, check the system)
- Failure case: what happens when the task partially fails?

### Default distribution (20 questions)
- Foundational Core: 5
- Architecture: 4
- Robustness: 3
- Edge Cases & Guardrails: 3
- High-Value Goals: 3
- Task Completion: 2 (skip if agent is retrieval-only)

Scale proportionally for more questions.

### 2-step mode: pause here for question approval

---

## STEP 3 — Define grader stacks (multiple graders per test)

Every test must have multiple graders. The graders are composed — they watch different aspects of the same response simultaneously.

### Available graders

| Grader | What it measures | Needs expected answer? |
|---|---|---|
| **General Quality** | Meaningful, relevant, complete, grounded in source? | No |
| **Compare Meaning** | Same meaning as expected answer, even if worded differently? | Yes |
| **Tool Use / Routing** | Did the right tool or topic fire? (observed, not enforced) | No — specify expected tool |
| **Keyword Match** | Does response contain required terms? | Yes — keywords list |
| **Custom** | Agent-specific rule: required format, required citation, required refusal, required structure | Optional |
| **Task Completion** | Did the agent complete the requested task end-to-end? | No — verify by checking artifact/system |
| **Retrieval Quality** | Did it cite the right source? Correct document? Correct language? | Yes — expected citation |
| **Analytical Depth** | Did it reason beyond retrieval — synthesize, compare, explain implications? | No |
| **Efficiency** | Were tool inputs well-formed? No wasted calls? Inputs inferred correctly without over-asking? | No |
| **Verbosity** | Depth appropriate to question complexity? Not too thin, not padded? | No |
| **Formatting** | Tables, markdown, headers, code blocks used correctly for the channel? | No |
| **Self-correction** | For NGO: were reasoning steps visible? Did it detect and fix errors? | No |
| **Refusal quality** | For edge cases: did it refuse correctly and explain why helpfully? | No |
| **Multi-intent coverage** | For multi-intent questions: did it address all distinct requests? | Yes — list of intents |

### Grader stack by bucket

Assign a default stack per bucket, then customize per question:

| Bucket | Default grader stack |
|---|---|
| Foundational Core | General Quality + Compare Meaning + Tool Use |
| Architecture | General Quality + Tool Use + Retrieval Quality (if knowledge) + Efficiency |
| Robustness | General Quality + Compare Meaning + Verbosity |
| Edge Cases | General Quality + Custom (refusal/clarification rule) + Refusal quality |
| High-Value Goals | General Quality + Analytical Depth + Multi-intent coverage + Formatting |
| Task Completion | Task Completion + General Quality + Custom (artifact verification rule) |

### Scoring scale (scores are aids for focusing analysis, not pass/fail gates)
- **5** Excellent — fully meets all grader criteria with specificity
- **4** Good — meets criteria with minor gaps
- **3** Partial — correct direction but shallow, incomplete, or missing one key element
- **2** Weak — partially wrong, missing key content, or poor quality
- **1** Poor — wrong answer, irrelevant, or fabricated
- **0** Failed — error, timeout, or inappropriate refusal

**Important:** Do not chase a single aggregate score. Report scores per grader per question. Use score *patterns* (e.g. "General Quality consistently 4+ but Analytical Depth 2–3") to focus qualitative analysis.

### 2-step mode: pause here for grader stack approval

---

## STEP 4 — Run the tests

### CGO
URL: `https://copilotstudio.microsoft.com/environments/<envId>/bots/<botId>/overview`  
New conversation per bucket boundary (reset context after 8–10 questions).  
Capture: full response text, topic/flow names called (visible in test panel), render type, timing.

### NGO
URL: `https://copilotstudio.preview.microsoft.com/environments/<envId>/agents/<botId>`  
Preview tab → New chat.  
Input: `document.execCommand('insertText', false, question)` — React-compatible.  
Send: `document.querySelector('[data-testid="send-button"]').click()`  
Auth consent: auto-click "Allow" on first tool call.  
Capture: full response, inline reasoning step labels (tool call names as plain text before narrative), timing.  
Response complete: length stable for 2 consecutive 10s polls.

### Multi-turn tests
Send Turn 1, wait for response, then send Turn 2 in the SAME session (do NOT use New chat between turns).

### Task completion verification
After the agent claims to have completed a task, verify the artifact:
- File written to OneDrive: check via `m365_search_files`
- Dataverse record created: query Dataverse
- Email sent: check sent items
- External system action: verify via the connector

### Per-response record
```
Question: [text]
Bucket: [Foundational Core | Architecture | ...]
Grader stack: [General Quality, Compare Meaning, ...]
Expected answer: [text] [inferred/verified/user-provided]
Expected behavior: [tool name | should refuse | should complete task X]

Agent 1 response: [300 char preview]
Agent 1 tools called: [list in order]
Agent 1 behavior: [what it actually did]
Agent 1 task verified: [yes/no/n-a, how verified]
Agent 1 time: [seconds]
Agent 1 scores: { generalQuality: 4, compareMeaning: 3, analyticalDepth: 4, toolUse: 5 }
Agent 1 qualitative notes: [specific observations — what was good, what was missing]

Agent 2: [same structure]

Winner: [Agent1 | Agent2 | Tie | Both failed]
Key finding: [one sentence on the most interesting difference or agreement]
```

---

## STEP 5 — Analyze and score

### Aggregate by bucket — not a single total
For each bucket: mean score per grader per agent. Report differences.

### Qualitative narrative first
For each bucket, write 2–4 sentences describing:
- What the agents did well in this bucket
- Where the gap is and what it reveals about the architecture
- Any unexpected behaviors (self-correction, refusals, creative synthesis)

Scores support this narrative — they don't replace it.

### Pattern analysis
Look for cross-cutting patterns:
- "Agent 1 consistently calls tools with better-formed inputs (Efficiency 4.8 vs 3.1)"
- "Agent 2 consistently refuses when it should answer (Refusal Quality 1.9 vs 4.2)"
- "Both agents agree on numerical answers but Agent 1 provides more analytical context"
- "Agent 2 is faster by 40% but shallower on Analytical Depth"

---

## STEP 6 — Generate comparison report (HTML)

Self-contained HTML using Clawpilot theme variables. Must include theme detection script. Sections:

1. **Agent Profiles** — type, model, tools, knowledge, skills, inferred purpose
2. **Test Design Summary** — how questions were generated, what sources were sampled, bucket distribution
3. **Bucket Score Overview** — side-by-side scores per bucket per grader (not a single total)
4. **Qualitative Findings** — narrative per bucket, key patterns
5. **Question Detail** — each question with both responses, grader scores, qualitative notes, key finding
6. **Agreements** — where both agents gave consistent answers (validates the expected answer)
7. **Divergences** — where answers differed materially and why
8. **Tool / Architecture Analysis** — what tools fired, in what order, with what inputs
9. **Task Completion Results** — tasks attempted, tasks verified, partial failures
10. **How to Improve Each Agent** — (see below)
11. **Platform Improvement Opportunities** — (see below)
12. **Evaluation Quality Notes** — (see below)
13. **CGO Starter Test Sets** — CSV download links per bucket

### Section 10 — How to Improve Each Agent

For each agent, generate specific, actionable improvement recommendations grounded in:
- **What you observed** in the test run (low scores, missed tools, shallow answers, fabricated data, poor formatting)
- **What you know about CGO/NGO best practices** (from the `/cgo-nl2query-patterns`, `/ngo-nl2query-patterns`, `/copilot-studio-new-orchestrator` skills)

Organize by improvement type:

**Instructions improvements:**
- What is missing, over-specified, or wrong in the current system prompt?
- Does it use the right persona framing? Is schema delivery appropriate (table names only vs _metadata table)?
- Does it have clear output instructions for the channel? (markdown-only for NGO, adaptive cards for CGO)
- For NGO: are instructions plain ASCII with no escaped underscores or zero-width unicode?

**Tools improvements:**
- Are the right tools connected? Missing any?
- For NGO: are PA flows used as tools? If so, are they failing? Should they be replaced with direct connector actions?
- For CGO: are flow tools using `mode: Invoker` for RLS enforcement?
- Is there a refresh strategy that makes sense? (CGO: conversation variable guard; NGO: external cadence or user-triggered only)

**Skills improvements (NGO):**
- What skills would reduce reasoning time on common question patterns?
- Are there validated DAX/query patterns from this run that should be encoded as skills?
- Is there a schema-definitions skill? A domain-specific business rules skill?

**Knowledge improvements:**
- Are the right knowledge sources connected?
- Is there a `_metadata` table pattern that would improve schema delivery?
- Citation quality issues observed? Missing sources?

**Architecture pattern improvements (CGO):**
- Are there topics that could be simplified?
- Is the refresh-once-per-conversation guard implemented?
- Could the output composition (chart + narrative + follow-ups) be improved?

**Model and configuration:**
- Is the right model selected for the complexity of questions this agent receives?
- Would Opus 4.8 improve self-correction on complex multi-table joins?

Rate each improvement by impact: **High** (would materially improve test scores), **Medium** (quality improvement), **Low** (polish).

### Section 11 — Platform Improvement Opportunities

Based on what was observed in the test run AND known platform limitations, generate a list of product improvement suggestions:

For CGO:
- What prevented the agent from doing something the test revealed users want?
- Are there platform constraints that required workarounds?

For NGO:
- **Inline chart rendering** — blocked; all visual output requires file delivery
- **PA flows as tools reliability** — HTTP 500 errors in some environments
- **Conversation variables** — no session state; forced to use instruction-only refresh guards
- **PAC CLI push on cliagent-1.0.0** — crashes with ArgumentOutOfRangeException
- **In-product Evaluation** — not yet available for NGO
- **Skills via PAC CLI** — no `pac copilot skill` command; UI-only
- Any NEW limitations discovered in this test run that weren't previously documented

Format as a prioritized list with: limitation, user impact, workaround used, suggested product fix.

### Section 12 — Evaluation Quality Notes

Honest self-assessment of this test run's reliability:
- Which expected answers were `[verified]` vs `[inferred]` — and how confident are we?
- Were any scores revised after initial assignment? Why?
- Any test harness anomalies that affected scores? (e.g. intermediate reasoning captured)
- Which bucket has the weakest coverage and should be expanded next run?
- Are there question types this run didn't cover that should be added?
- Recommended changes to the question set for the next run on these agents

---

## STEP 7 — Generate evaluation learnings file (skill addendum for this evaluator)

After each run, write a new skill file specific to the agent-pair being evaluated. This file accumulates across runs so each subsequent evaluation of the same agents is better informed and does not repeat mistakes.

**The learnings file is for the evaluator (this skill), not for the agents being tested.**

### What to capture

For each quality gap, miscalibration, or test design problem discovered during this run:

```markdown
## Evaluation learnings: [Agent1-name] vs [Agent2-name]
Last updated: [date]

### Test design corrections

[ISSUE]: [what went wrong — e.g. "intermediate reasoning captured instead of final answer for NGO Q4/Q15"]
[CAUSE]: [why it happened — e.g. "response poller captured content before final answer replaced preamble"]
[FIX]: [what to do differently — e.g. "add 3s extra wait after last tool call label appears before capturing response"]
[AFFECTED BUCKET]: Architecture

### Grader calibration corrections

[QUESTION]: [which question was miscalibrated]
[ORIGINAL SCORE]: [what was scored]
[REVISED SCORE]: [what it should have been]
[REASON]: [why it was wrong — e.g. "Q4 NGO scored 2/5 but was a harness anomaly not agent failure; true score 4/5"]
[RULE FOR NEXT RUN]: [how to avoid this — e.g. "if response is the agent listing available tables in response to a non-schema question, mark as HARNESS_ANOMALY and re-run"]

### Known answer divergences (do not use as expected answers)

[QUESTION]: [question where agents disagreed]
[AGENT1 ANSWER]: [what CGO returned]
[AGENT2 ANSWER]: [what NGO returned]
[STATUS]: Unresolved divergence — warrants manual verification of DAX
[NOTE]: Do not pre-populate expectedResponse for this question in test CSVs

### Verified expected answers (confirmed across runs)

[QUESTION]: [question]
[EXPECTED ANSWER]: [confirmed value]
[CONFIDENCE]: High — confirmed by both agents across 2+ runs
[GRADER CRITERIA]: [specific scoring rule to use]

### Regression test additions

[QUESTION]: [question that revealed a failure]
[EXPECTED RESPONSE]: [correct answer]
[BUCKET]: Foundational Core
[GRADER STACK]: General Quality + Compare Meaning
[RATIONALE]: [why this test should now be in the permanent foundational set]
```

### File naming convention

`<outputDir>/evaluation-learnings-[agent1]-[agent2].md`

Also save to the project skills folder:
`C:\src\[project]\skills\[agent1]-[agent2]-eval-learnings\SKILL.md`

When this skill is invoked for the same agent-pair again, load the learnings file first. It overrides or supplements generic defaults for that pair.

### Regression test additions (for CGO test CSVs)
For each newly confirmed answer or failure, append to the foundational core CSV:
```
New foundational core test:
  Question: [the question]
  expectedResponse: [correct answer, now verified]
  gradingCriteria: [specific criterion]
  rationale: [what this test catches]
```

---

## STEP 8 — Output CGO test sets (CSV)

One CSV per bucket. Format for Copilot Studio in-product Evaluation import:
```csv
question,expectedResponse
"[question]","[expected answer or blank for general quality]"
```
- Max 500 chars per question, max 100 rows per file
- `expectedResponse`: include when `[verified]` or high-confidence `[inferred]`; leave blank otherwise
- **Keywords column**: NOT in the template — add manually in Copilot Studio UI after import for keyword-match test methods

### Custom grader output (for knowledge tests and task tests)
Per test case that needs a custom grader:
```
Question: [text]
Custom grader instructions for Copilot Studio:
"[Specific pass criteria. Example: 'The response must cite [source]. 
Must include [key fact]. Must NOT contain [wrong claim]. 
Score 5 if all criteria met. Score 3 if answer correct but citation missing. 
Score 0 if answer is wrong or fabricated.']"
```

### AI prompt templates for generating more tests (output as test-prompts.md)

**Foundational Core:**
```
Generate [N] must-pass test questions for a [AGENT DOMAIN] agent that test its core promise.
For each: provide expectedResponse (exact or paraphrase of correct answer).
Verify answers against [DATA SOURCE / KNOWLEDGE BASE] before including.
Format: CSV question,expectedResponse
```

**Architecture — knowledge retrieval:**
```
Generate [N] questions where the correct answer comes specifically from [SOURCE NAME].
For each: expectedResponse + expectedCitation (document/section/table name).
Format: CSV question,expectedResponse,expectedCitation
```

**Architecture — tool use:**
```
Generate [N] questions that each require calling [TOOL NAME] to answer.
For each: expectedTool + expectedResponse (what the tool should return).
Format: CSV question,expectedTool,expectedResponse
```

**Robustness:**
```
Take these questions: [PASTE QUESTIONS]
For each, generate 3 phrasings: formal, casual, with irrelevant context added.
All phrasings should produce the same expected answer.
Format: CSV question,expectedResponse,originalQuestion
```

**Edge Cases & Guardrails:**
```
Generate [N] edge-case questions for a [AGENT DOMAIN] agent.
Categories: out-of-scope (SHOULD REFUSE), invalid input (SHOULD HANDLE GRACEFULLY),
adversarial (SHOULD NOT HALLUCINATE), ambiguous (SHOULD CLARIFY).
Format: CSV question,expectedResponse,caseType
```

**High-Value Goals (multi-step):**
```
Generate [N] complex multi-intent questions for a [AGENT DOMAIN] agent.
Each question should require [2–5] tool calls or reasoning steps to answer fully.
For each: expectedToolChain (tool1 → tool2 → ...) + expectedResponse.
Format: CSV question,expectedToolChain,expectedResponse
```

**Task Completion:**
```
Generate [N] task-completion test cases for a [AGENT DOMAIN] agent that can [TASK CAPABILITIES].
For each: the user request + how to verify completion (artifact check, system query).
Format: CSV question,verificationMethod,expectedOutcome
```

---

## STEP 9 — Save all outputs

```
<outputDir>/
  comparison-report.html          ← interactive report (Clawpilot-themed)
  agent1-profile.md               ← discovered config + data sampling results
  agent2-profile.md
  generated-questions.md          ← all questions with expected answers, grader stacks, bucket
  raw-responses.json              ← full response captures for both agents
  test-foundational-core.csv      ← import into Copilot Studio in-product eval
  test-architecture.csv
  test-robustness.csv
  test-edge-cases.csv
  test-high-value-goals.csv
  test-task-completion.csv
  custom-graders.md               ← custom grader specs for Copilot Studio
  evaluation-learnings-[a1]-[a2].md  ← evaluator skill addendum: test corrections, grader recalibrations, verified answers, regression additions for next run on this agent-pair
  regression-additions.md         ← new test cases to add to foundational core after failures
  test-prompts.md                 ← AI prompt templates for generating more tests per bucket
  summary.md                      ← one-page: bucket scores, key findings, top 3 recommendations
```

---

## CDP Browser Notes (for NGO automation)

### What the user must provide
Before the skill can test NGO via CDP, ask the user for:
1. **Agent test URL** — the Copilot Studio test chat URL for their NGO agent. Format:
   `https://copilotstudio[.preview].microsoft.com/environments/<envId>/agents/<botId>/canvas`
   (Tip: open the agent in Copilot Studio, click "Test your agent" — copy the URL from the iframe or use the /agents/<botId> path directly.)
2. **Whether they are already signed in** to that environment in Edge (or can sign in before the test run starts).

### Environment prerequisites (any valid environment)
- Copilot Studio environment with the NGO agent **published** (draft is not testable via canvas URL)
- User must be **signed in** to that environment in the Edge profile that will be launched for CDP
- The agent must have Power BI tools connected — **the skill checks this automatically** (see Tool Check below)
- No DLP policy blocking the Power BI connector in that environment

### Tool check (auto-run before testing NGO)

Use the Dataverse API to check whether the agent already has Power BI tools. If missing, the skill adds them via CDP rather than stopping.

```powershell
# Check existing tools via Dataverse botcomponent query
$dvToken = Get-DVToken   # az account get-access-token --resource $orgUrl ...
$dvHeaders = @{ Authorization = "Bearer $dvToken"; "Content-Type" = "application/json" }

$components = (Invoke-RestMethod `
    "$orgUrl/api/data/v9.2/botcomponents?`$filter=_parentbotid_value eq '$botId'&`$select=name,componenttype" `
    -Headers $dvHeaders).value

$pbiTools = $components | Where-Object { $_.name -like "*query*dataset*" -or $_.name -like "*executeQueries*" }

if ($pbiTools.Count -ge 2) {
    Write-Host "✅ Power BI tools present ($($pbiTools.Count) found) — proceeding with test"
} else {
    Write-Host "⚠️  Power BI tools missing — adding via CDP..."
    # Proceed to CDP tool-add block below
}
```

**If tools are missing — add via CDP:**
Navigate to: `https://copilotstudio[.preview].microsoft.com/environments/<envId>/agents/<botId>`

Add these 3 tools via Tools "+" → Connectors → Power BI:
1. **"Run a query against a dataset"** — primary DAX executor
2. **"Run a json query against a dataset"** — DAX variant/fallback
3. *(optional)* **"Refresh a dataset"** — add but disable in instructions if environment is CDX/managed

Search for each by name in the connectors panel. Each is a single click → Add.

After adding, re-run the Dataverse check above to confirm before testing.

### Launch pattern (environment-agnostic)

```powershell
# Use a dedicated CDP profile (separate from the user's main Edge — avoids session conflicts)
# The profile path can be anything; use a unique folder per environment if needed
$profileName = "copilot-studio-cdp"   # user can override
$p = "$env:LOCALAPPDATA\CopilotStudioCDP\$profileName"
New-Item -ItemType Directory -Path $p -Force | Out-Null
Start-Process msedge.exe "--remote-debugging-port=9333 --user-data-dir=`"$p`" --no-first-run about:blank"
Start-Sleep 5
# Then navigate to the agent test URL (user must sign in on first use of this profile)
```

### Sign-in flow
- On first launch of a new profile, the user will need to sign in to M365/Entra in the browser window that opens.
- After sign-in the profile is saved; subsequent runs skip this step.
- If the user is already signed in on their main Edge, they can copy cookies — but a fresh profile is simpler.

### CDP helper (unchanged)

```powershell
function Send-CDP($tabId, $method, $params = "{}") {
    $ws = [System.Net.WebSockets.ClientWebSocket]::new()
    $ws.ConnectAsync([Uri]"ws://localhost:9333/devtools/page/$tabId", [System.Threading.CancellationToken]::None).Wait()
    $msg = "{`"id`":1,`"method`":`"$method`",`"params`":$params}"
    $b = [System.Text.Encoding]::UTF8.GetBytes($msg)
    $ws.SendAsync([System.ArraySegment[byte]]::new($b), [System.Net.WebSockets.WebSocketMessageType]::Text, $true, [System.Threading.CancellationToken]::None).Wait()
    $buf = [byte[]]::new(131072)
    $r = $ws.ReceiveAsync([System.ArraySegment[byte]]::new($buf), [System.Threading.CancellationToken]::None).GetAwaiter().GetResult()
    [System.Text.Encoding]::UTF8.GetString($buf, 0, $r.Count) | ConvertFrom-Json
}
```

Response stability: poll `document.body.innerText` every 10s; complete when length is stable for 2 consecutive polls.
Tool call detection (NGO): extract tool call labels that appear as plain-text prefixes before the narrative in the response.



