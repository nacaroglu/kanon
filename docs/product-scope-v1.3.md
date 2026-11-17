# Kanon — v1 Product Scope

**Version:** 1.3 — Expanded Scope  
**Date:** November 16, 2026  
**Status:** Product scope agreed — 38 decisions confirmed  
**Development model:** Solo developer  
**Target delivery:** 6–8 weeks, extendable  
**Primary objective:** Demonstrable AI Engineering portfolio project

---

## Changes in 1.3

Section 10 (Evaluation) is rewritten. The choice made in D19, a structured automated suite, stands; four decisions make it rigorous.

- **D35 — Evaluation language.** English primary, Turkish secondary subset.
- **D36 — Data tiers.** Synthetic with labels fixed by construction, handwritten, and a small non-gating real-data slice; all labels verified by a person.
- **D37 — Measurement protocol.** Claim-level measurement at roughly 60 scenarios and 300 claims; development, frozen test and regression splits; thresholds fixed before the first test run; baselines, comparisons and repeated runs.
- **D38 — Judge calibration.** LLM judge calibrated against about 50 hand-labeled proposals; human approval rate becomes observational.
- Related updates in sections 12, 14, 15, 16 and 17.

## Changes in 1.2

- **D33 — Not-covered outcome.** A fourth finding outcome reports relevant claims that no approved procedure addresses, so additions are no longer hidden under "no contradiction" (3.3).
- **D34 — Source effective date.** Every authoritative source carries an effective date; proposals based on a source older than the target procedure's last approved change carry a staleness warning that must be acknowledged before approval (2.5).
- Related updates in sections 1.4, 1.5, 3.4, 4.2, 5.1, 6.3, 7.2, 7.3, 10, 11, 12, 14, 15, 16 and 17.

---

## 1. Product Overview

### 1.1 Product Definition

Kanon is a self-hosted, AI-powered system for maintaining trustworthy organizational procedures.

It analyzes new documents against a repository of approved procedures, detects contradictions, proposes evidence-backed modifications, and publishes human-approved changes to Git.

AI agents and applications can retrieve the resulting approved procedures through MCP and REST interfaces.

### 1.2 Target User — Decision 1 (A)

**Primary users:** AI Engineers and Software Developers building AI agents that consume organizational knowledge.

These users need a reliable mechanism to ensure agents operate using approved, consistent, and traceable procedures.

v1 is designed primarily for individual developers rather than enterprise compliance teams or nontechnical business users.

### 1.3 Core Problem — Decision 2 (A)

AI agents may use outdated, contradictory, or unverified organizational procedures.

This can lead to:

- Incorrect agent decisions.
- Inconsistent application of organizational rules.
- Difficulty distinguishing authoritative knowledge from informal statements.
- Limited traceability of the information influencing agent behavior.
- Uncontrolled propagation of outdated knowledge.

**Problem statement:**

> AI Engineers need a reliable way to detect inconsistencies in organizational knowledge and ensure their agents consume human-approved procedures.

### 1.4 Primary Job — Decision 3 (A)

**Detect contradictions and propose evidence-backed fixes.**

Given newly submitted information, Kanon must:

1. Understand relevant claims in the source.
2. Locate related approved procedures.
3. Identify meaningful contradictions.
4. Determine whether a change can be proposed.
5. Generate minimal, evidence-backed modifications.
6. Validate the proposed changes.
7. Require human approval before publication.

Relevant claims that no approved procedure addresses are reported as not-covered findings. They do not produce change proposals in v1.

Kanon is not intended to be a general-purpose enterprise search engine or document chatbot.

### 1.5 v1 Product Principles

- **Approved knowledge is authoritative.** Newly uploaded information cannot silently replace approved procedures.
- **Evidence before modification.** Every proposed change must reference supporting source material.
- **Human control.** AI can recommend changes, but cannot independently publish them.
- **Explicit uncertainty.** Ambiguous information must not be presented as a definitive contradiction.
- **Explicit recency.** A source does not override an approved procedure merely because it was uploaded later. Effective dates are compared, and an older source is flagged.
- **Traceability.** Published changes must be connected to their original evidence and review history.
- **Developer-first.** Local installation and agent integration are primary requirements.

---

## 2. Knowledge Sources and Ingestion

### 2.1 Initial Knowledge Base — Decision 23 (A)

Kanon must initialize its approved procedure repository from an existing Git repository.

Requirements:

- Import a Git repository containing approved Markdown procedures.
- Treat imported procedures as the initial authoritative knowledge base.
- Preserve existing procedure content and Git history.
- Index imported procedures for retrieval and contradiction detection.
- Provide a sample repository for demonstration and testing.

**Boundary:** The initial repository is trusted by configuration. Kanon does not attempt to independently certify that all imported procedures are legally or factually correct.

### 2.2 Document Submission — Decision 4 (A)

Document ingestion is triggered manually.

Users submit source files using the Web UI or CLI.

Requirements:

- Accept a file submission.
- Associate source metadata with the submission.
- Start an analysis job.
- Return a job identifier.
- Make progress and results available after processing.

Live synchronization and continuously monitored connectors are excluded from v1.

### 2.3 Supported Document Types — Decision 5 (D)

v1 must support these input categories:

| Input | Requirement |
|---|---|
| Markdown | Parse text and preserve document structure |
| TXT | Parse plain text |
| PDF | Extract machine-readable text |
| DOCX | Extract text and relevant structural information |
| Meeting transcripts | Process exported textual transcripts |
| Ticket exports | Process supported file-based ticket exports |

Every supported input must be transformed into a representation that allows claims to be traced back to the original source.

**Constraints:**

- Scanned PDFs requiring OCR are excluded.
- Audio transcription is excluded.
- Meeting transcripts must already exist as files.
- Ticket exports are files, not live Jira or other ticket-system integrations.
- Exact ticket export formats remain to be specified.

### 2.4 Source Authority — Decision 25 (B)

Each uploaded source must be explicitly classified by the user.

**Authoritative**

Represents information considered eligible to justify a procedure change.

Examples might include a formally accepted decision record or approved policy amendment.

**Informational**

Represents context that may contain useful information but should not independently authorize modifications.

Examples might include informal meeting discussions or unverified ticket comments.

Behavior:

- Both categories may be analyzed for contradictions.
- Only authoritative sources may generate actionable procedure change proposals.
- Informational sources may produce contradiction findings without actionable diffs.
- Source classification must be retained with the submission.
- Human approval remains mandatory even for authoritative sources.

**Important:** Declaring a source authoritative is an assertion by the user, not automatic proof of its correctness.

### 2.5 Source Effective Date — Decision 34

Each source carries an effective date: the date from which its content is considered to apply.

Requirements:

- The user provides the effective date at submission.
- The effective date is mandatory for authoritative sources and optional for informational sources.
- Kanon does not silently infer an effective date from document content or from the upload time.
- The effective date is retained with the submission.

**Staleness check**

For every contradiction, Kanon compares the source effective date with the date of the last approved change to the target procedure.

| Condition | Behavior |
|---|---|
| Source effective date is on or after the procedure's last approved change | Normal processing |
| Source effective date is earlier than the procedure's last approved change | The finding and any proposal carry a staleness warning |
| Source has no effective date (informational only) | Recency is reported as unknown |

A proposal with a staleness warning may still be generated, but it cannot be approved without explicit acknowledgment by the reviewer. The acknowledgment is recorded in the audit history.

**Boundaries:**

- The date of a procedure's last approved change is taken from the Git history of its file.
- For imported procedures, the commit date is a proxy for the approval date.
- v1 compares dates at file level, not passage level. A recent unrelated edit to the same file can therefore trigger a warning.
- The effective date is an assertion by the user, like source authority.

---

## 3. AI Analysis and Contradiction Detection

### 3.1 Claim Extraction

Kanon must extract meaningful procedural claims from source documents.

Supported claim categories include:

- Decisions
- Rules
- Exceptions

Each extracted claim must retain a link to the source passage that supports it.

The system must not treat instructions embedded inside source documents as commands governing its own behavior.

### 3.2 Knowledge Retrieval — Decision 9 (C)

**Selected approach: Hybrid retrieval (keyword + vector).**

For every relevant extracted claim, Kanon searches approved procedures using a combination of:

- Keyword-based matching to identify exact terms and identifiers.
- Vector similarity to identify semantically related procedures.

Requirements:

- Retrieve candidate procedures relevant to a claim.
- Provide the retrieved evidence to contradiction analysis.
- Retain retrieval results for traceability.
- Support retrieval evaluation using known relevant procedures.

The main objective is to reduce the risk of missing the procedure that a new claim contradicts.

### 3.3 Contradiction Classification — Decisions 3, 20, 21 and 33

Every analyzed claim must be assessed against relevant approved knowledge.

The result must support four outcomes:

**1. Contradiction**

The source claim conflicts with an approved procedure.

The result should identify:

- The conflicting statement from the source.
- The conflicting approved procedure.
- Supporting references.
- An explanation of the conflict.

An actionable change proposal may be generated only when the source is authoritative and validation requirements are satisfied.

If the source is older than the procedure's last approved change, the finding carries a staleness warning (see 2.5).

**2. No contradiction found — Decision 20 (B)**

No contradiction was identified in the analyzed material. The claim is consistent with, or already covered by, approved procedures.

Kanon must provide:

- Relevant retrieved procedures.
- Supporting references.
- A concise explanation of the result.

This result must not be presented as proof that the document is free of all contradictions.

**3. Uncertain — Decision 21 (B)**

The available evidence does not justify a confident classification.

Requirements:

- Mark the finding as uncertain.
- Explain the ambiguity.
- Retain the relevant evidence.
- Allow manual examination.
- Do not generate an actionable diff while the finding remains uncertain.

Uncertainty must not be silently converted into an approval-ready proposal.

**4. Not covered — Decision 33**

The source contains a relevant procedural claim that no approved procedure addresses, and it conflicts with none of them.

Typical cases are a new rule, a new exception to an existing procedure, or a topic with no procedure at all.

Requirements:

- Mark the finding as not covered.
- Identify the nearest related approved procedures, if any.
- Explain why the claim is not considered covered.
- Retain the supporting source evidence.
- Allow manual examination.
- Do not generate an actionable diff in v1.

A not-covered claim must not be reported as "no contradiction found". The two outcomes answer different questions: one says the knowledge base already agrees, the other says it is silent.

### 3.4 Change Proposal Generation — Decision 6 (B)

For eligible contradictions, Kanon generates an evidence-backed modification proposal.

Every proposal must contain:

- Target approved procedure.
- Identification of the conflicting content.
- Proposed minimal modification.
- Diff showing the change.
- Explanation of why the change is necessary.
- References to supporting source passages.
- Validation outcome.
- Source effective date and staleness status.
- Review status.

**Minimal-diff requirement:**

The proposed modification should change only the content necessary to resolve the identified contradiction.

Kanon should avoid rewriting entire sections when a smaller modification is sufficient.

A proposal is never automatically equivalent to an approved change.

### 3.5 Multiple Contradictions — Decision 24 (A)

**One independent proposal per contradiction.**

If one uploaded document contradicts multiple procedures, Kanon generates separate proposals.

Example:

A meeting transcript contains three authoritative decisions that contradict two approved procedures.

Kanon may generate three independent proposals, including multiple proposals targeting the same procedure.

Each proposal must have:

- Its own evidence.
- Its own diff.
- Its own validation outcome.
- Its own approval or rejection decision.
- Its own audit trail.

This allows a reviewer to accept one change while rejecting another.

If multiple approved proposals target overlapping content, the system must prevent a stale or invalid diff from being applied silently.

---

## 4. AI Quality Assurance and Security

### 4.1 Independent AI Review — Decision 10 (B)

All actionable change proposals must pass an independent LLM review step and deterministic checks before human approval.

The reviewer assesses whether:

- Proposed changes are supported by the cited evidence.
- The proposal addresses the identified contradiction.
- Unsupported statements have been introduced.
- Suspicious instructions from source material are influencing the proposal.

The independent reviewer is a quality gate, not an approval authority.

### 4.2 Deterministic Validation

Minimum checks include:

- Proposed diff is syntactically valid.
- Proposed diff applies to the expected procedure version.
- Required source references exist.
- Required proposal metadata is present.
- An effective date is present for authoritative sources.
- The staleness comparison has been computed against the expected procedure version.
- Resulting procedure content remains structurally valid.

Exact Markdown metadata conventions will be specified separately.

A failed validation must be visible to the user and must prevent the affected proposal from being approved in its invalid state.

### 4.3 Security Guardrails — Decision 28 (A)

**Selected level: Basic security guardrails.**

v1 must include:

- File validation during ingestion.
- Separation of untrusted source content from system instructions.
- Prompt injection defenses during AI processing.
- Independent review for suspicious instructions.
- Validation before applying proposed changes.
- Protection against source content directly controlling Git operations.

Uploaded documents and historical rejection feedback must be treated as untrusted content, not as privileged instructions.

**Limitations:** These controls reduce risk but do not guarantee protection against every prompt injection attack.

Advanced adversarial security frameworks and extensive security benchmarking remain outside v1.

---

## 5. Human Review and Approval

### 5.1 Approval Model — Decision 7 (A)

**Single-user approval.**

The developer may inspect, approve, or reject individual change proposals.

Requirements:

- Display the target procedure.
- Show the proposed diff.
- Display supporting source evidence.
- Show the contradiction explanation.
- Display validation results.
- Display the source effective date and any staleness warning.
- Allow explicit approval or rejection.
- Record the review decision.
- Require explicit acknowledgment before a proposal with a staleness warning can be approved.

There is no mandatory separation between the person submitting a document and the person approving a proposed change.

### 5.2 Proposal Lifecycle

The proposal workflow must distinguish at least:

- Proposed / pending validation
- Validation failed
- Awaiting review
- Approved
- Rejected
- Published

An approved proposal is not considered published until the Git modification and required indexing operations are completed successfully.

The exact internal state model will be defined during technical specification.

### 5.3 Rejected Proposals — Decision 22 (B)

Rejected proposals become feedback for future analyses.

Requirements:

- Preserve the rejected proposal.
- Record the rejection reason.
- Retain its supporting evidence.
- Make relevant past rejection cases retrievable during subsequent analyses.

Example:

A developer rejects a proposed change because the source describes a temporary exception rather than a permanent rule.

Future analyses may use that rejection as contextual evidence when evaluating similar claims.

**Limits:**

- Rejections do not automatically modify approved procedures.
- Rejections do not automatically change system instructions or prompts.
- Retrieved feedback cannot override source authority rules.
- Feedback does not guarantee that the same error will never recur.

---

## 6. Approved Knowledge Storage and Publication

### 6.1 Canonical Repository — Decision 8 (A)

**Git is the source of truth for approved procedures.**

Requirements:

- Store approved procedures as Markdown.
- Preserve Git version history.
- Apply approved changes through Git commits.
- Associate published changes with their originating proposal and evidence.
- Allow historical versions to be inspected.

Git is authoritative for approved procedure content. Other persistent records support processing, retrieval, and auditability.

### 6.2 Publishing Workflow — Decision 26 (A)

After a proposal is approved:

1. Verify the diff applies to the current procedure version.
2. Apply the approved change.
3. Create the corresponding Git commit.
4. Update the search index.
5. Record the publication event.
6. Make the updated procedure available through MCP and REST.

**Consistency requirement:**

An updated procedure must not be served as the new approved version until the corresponding search index update succeeds.

If indexing fails, Kanon must expose the failure and support recovery without silently serving inconsistent knowledge.

The precise transaction and recovery strategy remains an implementation decision.

### 6.3 Persistent Data — Decision 14 (A)

**Selected approach: Persist all analysis data.**

v1 must retain:

| Data | Purpose |
|---|---|
| Source files | Original evidence and reproducibility |
| Source metadata | Origin, type, authority, effective date, submission information |
| Extracted claims | Explain what the model identified |
| Retrieval results | Trace how relevant procedures were found |
| Analysis findings | Preserve classifications and explanations |
| Change proposals | Retain diffs and supporting evidence |
| Validation results | Explain quality-gate outcomes |
| Review decisions | Track approvals, rejections, and reasons |
| Audit events | Preserve the history of significant operations |
| Evaluation cases/results | Support quality measurement and regression analysis |

The approved Markdown content remains canonical in Git.

Persistent application records and retrieval metadata are maintained separately.

### 6.4 Auditability

The audit history must support answering:

- Which source triggered the analysis?
- Which approved procedure was affected?
- Which contradiction was identified?
- What change was proposed?
- What evidence supported it?
- Was it approved or rejected?
- What change was committed?
- When was the published procedure updated?

Because v1 has no authentication system, audit records cannot claim verified attribution to distinct authenticated users.

---

## 7. User Interfaces and External Access

### 7.1 Interface Strategy — Decisions 11 and 12

v1 includes four interfaces.

| Interface | Purpose | Scope |
|---|---|---|
| Web UI | Interactive human workflow | Upload, inspect jobs, review evidence and diffs, approve/reject |
| CLI | Developer terminal workflow | Submit, inspect results and job status, review/approve/reject |
| MCP | AI agent knowledge access | Read-only approved knowledge |
| REST API | Application knowledge access | Read-only approved knowledge |

The read-only restriction applies to the external knowledge-consumption interfaces.

The Web UI and CLI must support the internal write operations required for human approval and publishing.

### 7.2 Web UI — Decision 12 (C)

The Web UI must support:

- Initial repository setup.
- Manual file upload.
- Source authority selection.
- Source effective date entry.
- Analysis job status.
- Contradiction findings.
- No-contradiction explanations.
- Uncertain findings.
- Not-covered findings.
- Evidence inspection.
- Side-by-side or otherwise clearly readable diffs.
- Proposal approval and rejection.
- Review and publication status.
- Processing failures and manual retry.

The interface should emphasize reviewing evidence and approving precise changes rather than generic document browsing.

### 7.3 CLI — Decision 12 (C)

The CLI must provide the essential developer workflow:

- Initialize or configure the approved procedure repository.
- Submit source files for analysis, including authority classification and effective date.
- Inspect job progress and outcomes.
- Inspect proposed changes and evidence.
- Approve or reject individual proposals.
- Inspect failures and retry processing.

Exact command names and flags are not yet fixed.

The CLI does not need to duplicate every visual presentation feature of the Web UI.

### 7.4 MCP Interface — Decision 11 (C)

Kanon must provide read-only MCP access to approved procedures.

The initial tool capabilities are:

| MCP capability | Purpose |
|---|---|
| `search_procedures` | Find relevant approved procedures |
| `get_procedure` | Retrieve an approved procedure |
| `get_provenance` | Retrieve supporting provenance information |
| `list_recent_changes` | Retrieve recently published procedure changes |

These names follow the initial project proposal; exact schemas and response contracts remain to be specified.

MCP must not expose pending or rejected proposals as if they were approved procedures.

### 7.5 REST API — Decision 11 (C)

The REST API must provide read-only application access to the same approved knowledge.

Required capabilities:

- Search approved procedures.
- Retrieve an approved procedure.
- Retrieve provenance.
- List recent published changes.

MCP and REST should provide consistent authoritative content.

Exact endpoint paths, response schemas, and pagination behavior remain open.

---

## 8. Processing and Operational Reliability

### 8.1 Async Processing — Decision 13 (B)

**Selected approach: Asynchronous background jobs.**

Document submission must not require the client to remain connected until LLM analysis finishes.

Requirements:

- Create a job for each document submission.
- Return a job identifier.
- Track processing state.
- Make job status accessible through Web UI and CLI.
- Persist results and failures.
- Support review after analysis completes.

At minimum, jobs must distinguish queued, processing, completed, and failed states.

The specific background-job technology has not been selected.

### 8.2 Failure Handling — Decision 29 (A)

**Automatic retries plus manual retry.**

Requirements:

- Retry transient failures automatically, up to three times.
- Record retry attempts and failure details.
- Expose persistent failures to the user.
- Allow manual retry of failed processing.
- Avoid unintended duplicate publications or repeated application of the same approved change.

Retries must not bypass validation or human approval.

### 8.3 Model Configuration — Decision 18 (C)

v1 supports both cloud-hosted and locally hosted LLMs through an OpenAI-compatible model interface.

Requirements:

- Configure model endpoints.
- Configure required credentials for hosted models.
- Support a local inference configuration.
- Use one selected reference cloud model for initial quality validation.
- Allow local-model evaluation separately.

**Important limitation:** A local model being technically compatible does not imply that it will meet the same evaluation thresholds as the reference model.

---

## 9. Deployment and Technology

### 9.1 Deployment — Decision 17 (A)

**Local self-hosted using Docker Compose.**

Requirements:

- Install and run Kanon locally.
- Start required services through Docker Compose.
- Persist application data between normal restarts.
- Support local configuration of Git repositories and LLM endpoints.
- Provide clear setup and operation instructions.

Production cloud hosting, remote team access, and managed infrastructure are excluded.

### 9.2 Authentication — Decision 27 (A)

**Single-user, localhost only.**

v1 does not require:

- Login screens.
- User registration.
- Multi-user sessions.
- Role-based access control.
- SSO.
- Tenant isolation.

Network-facing services must remain restricted to localhost by default.

The local operator is trusted, but uploaded documents are not.

### 9.3 Technology Stack — Decision 31 (A)

The agreed v1 stack is:

| Layer | Technology |
|---|---|
| Backend and application API | Python + FastAPI |
| Persistent application data | PostgreSQL |
| Vector retrieval support | pgvector |
| Frontend | React |
| Approved procedure versioning | Git + Markdown |
| Packaging and local deployment | Docker Compose |
| LLM integration | OpenAI-compatible endpoints |
| Agent integration | MCP |
| Developer interface | CLI |

This is a technology selection, not a complete architecture specification.

The specific retrieval implementation, async job library, LLM orchestration framework, and application module boundaries are not yet decided.

---

## 10. Evaluation and Quality Measurement

### 10.1 Evaluation Strategy — Decisions 19 (B) and 37

**Structured automated evaluation suite, measured at claim level.**

Each scenario is one source document analyzed against a fixed snapshot of approved procedures. Expected results are labeled per claim, not per scenario.

Target size: approximately 60 scenarios containing approximately 300 labeled claims. This replaces the earlier 30–50 scenario target, which was too small to report rates with useful precision.

The dataset must include cases such as:

- Clear contradictions.
- No-change cases.
- Semantically related but nonconflicting statements.
- Ambiguous evidence.
- Claims not covered by any approved procedure.
- Authoritative sources older than the procedure they conflict with.
- Multiple contradictions in one source.
- Authoritative versus informational sources.
- Unsupported proposed changes.
- Rejected proposal feedback.
- Source instructions that attempt to influence analysis behavior.

Hard negatives are required: statements that resemble a contradiction but are not one, such as a paraphrase of an existing rule, the same rule applied to a different entity, or a temporary exception.

### 10.2 Evaluation Data — Decisions 35 and 36

**Language — Decision 35**

English is the primary evaluation language. Turkish is a secondary subset of roughly 15–20% of cases.

Results are reported overall and per language.

**Data tiers — Decision 36**

| Tier | Content | Role |
|---|---|---|
| A — Synthetic | Cases built by applying a known change to an approved procedure and generating a source document that carries it | Volume and balanced coverage of outcomes |
| B — Handwritten | 20–30 claims written by a person, without model assistance | Reduces dependence on model-generated phrasing |
| C — Real slice | 10–20 cases from the public change history of a real handbook | Checks that synthetic results carry over to real material |

Label rules:

- In Tier A the expected result is fixed by construction: the change is chosen first, the source text is generated afterwards. A model does not decide the label.
- Every label is verified by a person before the case is used.
- The model that generates synthetic sources must differ from the model under evaluation.

Tier C is reported separately and is not part of the release gate.

### 10.3 Splits and Threshold Procedure — Decision 37

The dataset is divided into three parts.

| Split | Use |
|---|---|
| Development | Tuning prompts, retrieval and validation logic |
| Test | Frozen. Used only to report results and to check acceptance thresholds |
| Regression | Grows from observed failures and labeled rejected proposals |

Rules:

- Closely related scenarios are kept in the same split.
- Numeric acceptance thresholds are fixed in writing after development-split results are known and before the first test-split run.
- Every test-split run is recorded.

Exact numeric acceptance thresholds have **not yet been approved**. The procedure above defines when and how they are set, so that targets are not chosen to match observed results.

### 10.4 Evaluation Metrics

Quality is measured per stage as well as end to end.

| Stage | Metric |
|---|---|
| Claim extraction | Recall and precision of extracted claims against labeled claims |
| Retrieval | Recall@k of the relevant approved procedure |
| Classification | Precision and recall per outcome across the four outcomes; false-positive rate for contradictions |
| Uncertainty | How often the system abstains, and accuracy on the claims it does classify |
| Evidence | Whether findings and proposals cite appropriate supporting evidence |
| Proposal | Whether the change resolves the contradiction, stays minimal, and leaves unrelated content untouched; unsupported-change rate |
| Independent review | How often the reviewer catches deliberately flawed proposals, and how often it rejects sound ones |
| Prompt injection | How often embedded instructions change the analysis result |
| Rejection feedback | Reduction in repeated errors, and any loss of correct findings it causes |
| End to end | Share of scenarios handled fully correctly; cost and processing time per document |

Additional rules:

- Rates are reported with confidence intervals.
- Human approval rate is reported as an observation only. With a single operator who is also the author, it is not an independent quality measure and is not part of the release gate.
- Staleness detection is deterministic and is verified by automated tests, not by statistical evaluation.

### 10.5 Judge Calibration — Decision 38

Some proposal qualities cannot be checked deterministically, in particular whether a change introduces unsupported content. These are assessed by an LLM judge.

Requirements:

- Approximately 50 proposals are labeled by hand.
- The judge is run on the same proposals and its agreement with the human labels is reported.
- Judge-based metrics are published only together with that agreement figure.
- The judge is recalibrated when the judge model or its instructions change.

### 10.6 Baselines, Comparisons and Stability — Decision 37

Results must be interpretable against reference points.

- **Baselines:** a trivial classifier that always answers "no contradiction", and a single-prompt approach without retrieval.
- **Retrieval comparison:** keyword-only, vector-only and hybrid.
- **Reviewer comparison:** the workflow with and without the independent LLM reviewer.
- **Model comparison:** the reference cloud model and at least one local model.
- **Stage isolation:** each stage is also measured with correct inputs from the previous stage, so that losses can be attributed to a specific stage.
- **Stability:** each configuration is run several times; the average and the variation between runs are reported.

Every run is recorded with its model, prompt version, retrieval configuration, dataset version and code version.

### 10.7 Quality Acceptance Criteria — Decision 30 (B)

**Selected success model: Functional demo + measurable AI quality.**

Success requires both:

1. A functioning complete workflow.
2. A reproducible evaluation demonstrating and quantifying system quality.

Release-gate metrics are computed on the frozen test split against thresholds fixed under 10.3.

### 10.8 Regression Evaluation

Kanon must make it possible to reuse labeled evaluation cases when prompts, models, retrieval behavior, or validation logic change.

Historical rejected cases may become evaluation scenarios after their expected outcomes are explicitly labeled.

Automatically rewriting system prompts based on rejections is not included.

---

## 11. End-to-End User Workflow

The main Kanon workflow consists of ten steps.

### Step 1 — Initialize

The developer imports an existing Git repository containing approved Markdown procedures.

Kanon indexes the approved knowledge base.

### Step 2 — Upload

The developer uploads a document through Web UI or CLI, selects its authority classification, provides its effective date, and starts processing.

Kanon creates an asynchronous analysis job.

### Step 3 — Extract

Kanon reads the source and extracts relevant rules, decisions, and exceptions, with traceable evidence.

### Step 4 — Retrieve

Kanon uses hybrid search to locate approved procedures relevant to the extracted claims.

### Step 5 — Classify

Kanon identifies contradictions, no-contradiction findings, uncertain findings, or not-covered findings.

Findings retain explanations and references.

### Step 6 — Propose

For each eligible authoritative contradiction, Kanon produces one independent, minimal, evidence-backed diff.

Informational, uncertain, and not-covered findings do not produce actionable diffs.

A proposal based on a source older than the target procedure's last approved change carries a staleness warning.

### Step 7 — Validate

The independent LLM reviewer and deterministic checks assess the proposal.

Invalid proposals cannot advance to approval.

### Step 8 — Review

The developer inspects the diff, evidence, validation outcome, and any staleness warning, then approves or rejects the proposal.

Rejected proposals and their reasons are retained for future analysis context.

### Step 9 — Publish

Approved changes are applied and committed to Git.

The search index is updated before the new version is made available.

The publication is recorded in the audit history.

### Step 10 — Consume and Evaluate

An AI agent retrieves approved knowledge through MCP, or an application uses REST.

Kanon's automated evaluation measures how reliably the analysis workflow performs.

---

## 12. Explicitly Out of Scope / Later

The following capabilities are intentionally excluded from v1.

### Enterprise and Collaboration

- Multi-tenancy
- Team-based accounts
- SSO and enterprise authentication
- Role-based permissions
- Mandatory maker-checker separation
- Multiple organization workspaces
- Managed cloud hosting

### Ingestion and Synchronization

- Live Slack, Jira, and Confluence connectors
- Continuous source synchronization
- Automated repository monitoring
- Scheduled/nightly document analysis
- OCR for scanned documents
- Audio transcription

### Advanced Knowledge Automation

- Automatic publication without human approval
- Automatic creation of missing procedures as a separate workflow
- Change proposals for not-covered claims, including additions to existing procedures
- Passage-level temporal validity tracking
- Autonomous prompt or rule modification
- Automatic reanalysis of all historical documents after each change
- Fully autonomous policy maintenance

### Integrations and Advanced Workflows

- GitHub/GitLab Pull Request approval workflows
- Complex review routing
- Enterprise knowledge search portals
- General-purpose document chatbot

### Advanced Evaluation and Security

- Large-scale historical handbook benchmark suite (the 10–20 case non-gating real-data slice in 10.2 is in scope)
- Large-scale model benchmarking
- Comprehensive adversarial red-team framework
- Production-grade enterprise security certification

These features require separate scope decisions for a future release.

---

## 13. Delivery Strategy

### 13.1 Development Budget — Decision 15 (B)

**Original target:** 6–8 weeks.

**Planning assumption:** Approximately 10–15 hours per week.

This is a target, not a strict cap.

### 13.2 Development Approach — Decision 16 (A)

**Vertical slice first.**

Development begins with the smallest complete working workflow.

An initial vertical slice should demonstrate:

- Repository initialization.
- A simple document input.
- Extraction and retrieval.
- Contradiction detection.
- One evidence-backed proposal.
- Human review.
- Git publication.

Additional agreed capabilities are introduced incrementally.

The purpose is to maintain a working, testable system while expanding coverage.

### 13.3 Final Scope Rule — Decision 32 (C)

**Preserve all agreed v1 functionality.**

If the original schedule is insufficient, extend delivery rather than silently removing requirements.

In particular, the following remain mandatory:

- Full agreed input coverage.
- Hybrid retrieval.
- Independent LLM review.
- Human approval.
- Git publication.
- Web UI and CLI.
- MCP and REST.
- Asynchronous processing and retries.
- Rejection feedback.
- Structured evaluation.

The incremental development approach determines implementation order, not which features are eventually included in v1.

---

## 14. Key Assumptions and Risks

### Assumptions

1. The imported Git repository represents the initial approved knowledge base.
2. Developers can meaningfully classify new sources as authoritative or informational.
3. Supported document formats contain extractable textual evidence.
4. Hybrid retrieval can identify relevant approved procedures sufficiently often.
5. LLMs can detect meaningful procedural contradictions with measurable accuracy.
6. Independent model review can reduce unsupported proposals.
7. A single local operator is sufficient for v1 governance.
8. Users can supply a meaningful effective date for authoritative sources.
9. The Git commit date of a procedure's last change is an acceptable proxy for its approval date.
10. Synthetic cases with labels fixed by construction are representative enough to guide development; the real-data slice tests this assumption.

### Key Risks

| Risk | Potential impact | Scope-level mitigation |
|---|---|---|
| Incorrect claim extraction | Downstream contradictions become unreliable | Evidence-linked extraction and evaluation |
| Missed retrieval | Real contradictions remain undetected | Hybrid search and recall measurement |
| False contradictions | Excessive review work and unsafe proposals | Explicit uncertainty and quality gates |
| Unsupported diffs | Incorrect procedure modifications | Independent review and human approval |
| Prompt injection | Source text influences system behavior | Untrusted-content boundaries and validation |
| Incorrect source authority | Unverified information leads to inappropriate proposals | Explicit authority classification and human approval |
| Outdated authoritative source | A newer approved procedure is reverted | Effective date, staleness warning, and explicit acknowledgment |
| Additions misreported as agreement | New rules and exceptions are lost | Separate not-covered outcome and classification accuracy measurement |
| Evaluation overstates quality | Reported results do not hold on real material | Frozen test split, thresholds fixed in advance, human-verified labels, real-data slice |
| Unreliable LLM judge | Proposal-quality metrics are not trustworthy | Calibration against hand-labeled proposals, agreement reported |
| Stale search index | Agents consume inconsistent procedure versions | Publish only after successful indexing |
| Rejection feedback contamination | Historical feedback causes new errors | Treat feedback as contextual evidence, not instructions |
| Scope and integration complexity | Schedule exceeds 8 weeks | Vertical slices and extendable delivery target |

---

## 15. v1 Success Criteria

### Functional Acceptance

v1 is functionally complete when a developer can:

1. Install and start Kanon locally using Docker Compose.
2. Import an existing approved Markdown Git repository.
3. Submit each supported source category through the available workflow.
4. Analyze source claims using hybrid retrieval.
5. Detect and explain a known contradiction.
6. Receive a minimal, evidence-backed change proposal.
7. Observe independent validation results.
8. Approve or reject individual proposals.
9. Publish an approved change through a Git commit.
10. Retrieve the updated approved procedure through MCP and REST.
11. Run the equivalent essential workflow using the CLI.
12. Inspect stored evidence, results, and audit history.
13. Recover from a transient processing failure through retry.
14. Inspect an uncertain result without an actionable diff.
15. Receive evidence-backed explanations for no-contradiction results.
16. Demonstrate that rejected proposals can inform a later analysis.
17. Inspect a not-covered finding, with its nearest related procedures, without an actionable diff.
18. Receive a staleness warning for a source older than the target procedure, and approve it only after explicit acknowledgment.

### AI Quality Acceptance

The system must:

- Run the claim-level evaluation suite defined in section 10 on the frozen test split.
- Report stage-level metrics with confidence intervals, overall and per language.
- Report the baselines, the retrieval, reviewer and model comparisons, and run-to-run variation.
- Report judge agreement with human labels from the calibration set.
- Meet the numeric thresholds fixed before the first test-split run.
- Report the real-data slice separately, without gating on it.
- Provide a repeatable way to compare results after model or prompt changes.

### Delivery Artifacts

The v1 release must include:

- Working source repository.
- Docker Compose installation.
- Developer documentation.
- Sample approved procedure repository.
- Sample analysis inputs.
- Automated tests and evaluation dataset.
- Reproducible evaluation report.
- Demonstration of the complete workflow.

### Definition of Done

> Kanon v1 is complete when a developer can run it locally, import approved procedures, detect and validate contradictions from supported documents, review and publish evidence-backed modifications, and retrieve the updated approved knowledge through MCP and REST — with measurable AI quality and traceable human decisions.

---

## 16. Open Technical Decisions

The 38 product scope decisions are complete. The following details are intentionally left for specification and implementation planning.

| Area | Still to define |
|---|---|
| Git | Repository structure, Markdown conventions, required metadata, commit conventions |
| Document ingestion | Exact ticket export formats, parser behavior, extraction error policy |
| Evidence | Source span representation and citation contract |
| Temporal validity | Future-dated sources, time zones, and procedures without usable Git dates |
| Not-covered findings | Boundary between not covered and no contradiction; presentation of nearest procedures |
| Retrieval | Keyword algorithm, embedding model, ranking and fusion behavior |
| LLM | Reference model, prompts, provider configurations, costs |
| Background jobs | Job execution technology, lifecycle, persistence, retry semantics |
| Database | Detailed schemas, migrations, indexing layout |
| Web UI | Screens, UI states, review interaction details |
| CLI | Command names, arguments, output formats |
| MCP | Exact tool schemas and responses |
| REST | Endpoint paths, request/response schemas, errors |
| Publishing | Git/index failure recovery and overlapping proposal handling |
| Evaluation | Case file format, claim-matching rules, numeric thresholds, number of repeated runs, selection of the real-data slice |
| Operations | File limits, retention policies, logs, backup and recovery conventions |

These are not additional approved product requirements. Any choice that materially changes the agreed v1 behavior must be evaluated against this scope.

---

## 17. Complete Decision Traceability

| ID | Decision | Choice |
|---|---|---|
| D01 | Target user | A — AI Engineers / Developers |
| D02 | Core problem | A — Unreliable knowledge |
| D03 | Primary job | A — Detect contradictions and propose fixes |
| D04 | Analysis trigger | A — Manual document upload |
| D05 | Supported sources | D — Markdown, TXT, PDF, DOCX, transcripts, ticket exports |
| D06 | Analysis output | B — Evidence-backed change proposals |
| D07 | Approval workflow | A — Single-user approval |
| D08 | Canonical storage | A — Git repository |
| D09 | Retrieval | C — Hybrid keyword + vector |
| D10 | AI validation | B — Independent LLM reviewer + deterministic checks |
| D11 | External knowledge access | C — MCP + REST |
| D12 | User interface | C — Web UI + CLI |
| D13 | Processing | B — Asynchronous jobs |
| D14 | Data retention | A — Persist all analysis data |
| D15 | Development budget | B — 6–8 weeks target |
| D16 | Delivery approach | A — Vertical slice first |
| D17 | Deployment | A — Local Docker Compose |
| D18 | LLM support | C — Local + cloud |
| D19 | Evaluation | B — Structured suite (size superseded by D37) |
| D20 | No-contradiction results | B — Explain with evidence |
| D21 | Ambiguity | B — Explicit uncertainty state |
| D22 | Rejections | B — Reuse rejection feedback |
| D23 | Initial knowledge base | A — Existing Git repository |
| D24 | Multiple contradictions | A — One proposal per contradiction |
| D25 | Source authority | B — Explicit classification |
| D26 | Publication | A — Git commit + index update |
| D27 | Authentication | A — Single-user, localhost |
| D28 | Security | A — Basic guardrails |
| D29 | Failure handling | A — Automatic + manual retry |
| D30 | Success | B — End-to-end demo + measurable AI quality |
| D31 | Technology | A — Python/FastAPI/PostgreSQL/pgvector/React |
| D32 | Final prioritization | C — Preserve complete agreed scope |
| D33 | Not-covered claims | Added in 1.2 — Fourth outcome, finding without diff |
| D34 | Source effective date | Added in 1.2 — Mandatory for authoritative sources, staleness warning with acknowledgment |
| D35 | Evaluation language | Added in 1.3 — English primary, Turkish secondary subset |
| D36 | Evaluation data tiers | Added in 1.3 — Synthetic, handwritten, non-gating real slice; human-verified labels |
| D37 | Measurement protocol | Added in 1.3 — Claim level, three splits, thresholds fixed in advance, baselines and repeated runs |
| D38 | Judge calibration | Added in 1.3 — About 50 hand-labeled proposals; approval rate observational |

**Decision coverage:** 38/38 incorporated.

**Final scope status:** Agreed. Ready for detailed product requirements, technical specification, and implementation backlog.