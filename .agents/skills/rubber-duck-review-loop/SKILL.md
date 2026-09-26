---
name: rubber-duck-review-loop
description: Iteratively rubber-duck review user-specified documents, evaluate and fix meaningful findings, and append separate Review and Response sections until the reviewer clears all high blockers or the round limit is reached. Use when the user asks for repeated review-fix-review rounds, iterative document hardening, or review until clearance.
---

# Rubber-Duck Review Loop

Run bounded **review-response rounds** over a fixed document set. One round is:

1. an independent rubber-duck reviewer examines the current documents
2. the reviewer opinion is appended to the log
3. the main agent evaluates and fixes findings
4. the response and validation are appended to the log

## Inputs

Resolve these inputs before Round 1:

| Input | Requirement and default |
|---|---|
| Documents | Required. Use every path the user specifies. Ask only when none are supplied. |
| Log path | Optional. Default: `<repository-root>/logs/<first-document-stem>_rubber_duck_review.md`; use the working directory when no repository exists. A supplied directory uses the same generated file name. |
| Reviewer model | Optional. Default: the highest-version available `claude-opus-*` model. Record the exact model used. |
| Maximum rounds | Optional. Default: `5`. It must be a positive integer. |

The maximum applies to rounds in the current invocation, not historical rounds
already present in an existing log.

## Initialize

1. Read repository context files that govern the documents, including
   `CONTEXT.md` and relevant ADRs when present.
2. Confirm every document exists and is readable.
3. Resolve relative log paths from the repository root, or the working
   directory when no repository exists. Replace characters that are invalid
   in a file name with `_`. Create the parent directory and file when absent.
   Append to an existing log; preserve all earlier rounds.
4. Find the highest existing round number. The first new round uses the next
   number.
5. Write the document list, reviewer model, maximum rounds, and stop conditions
   in a new log header when the file is new.

Redact secrets and customer-sensitive information from reviewer output and log
entries. Preserve the technical finding after redaction.

## Round

### 1. Review

Launch one `rubber-duck` agent with the resolved reviewer model. Give it:

- every document path
- repository context sources
- the review log
- the current round number
- the rules below

The reviewer:

- reads the current documents and prior rounds
- treats earlier responses as claims to verify
- reports a prior issue again only when its fix is incomplete, incorrect, or
  regressed
- checks contradictions, ambiguity, invalid examples, source drift, security,
  interoperability, evidence gaps, impossible requirements, and avoidable
  complexity
- verifies external protocol claims against current primary sources
- runs structural or schema probes when useful
- does not edit files
- omits trivial style findings

Each finding contains:

1. stable ID: `R<round>-H<n>`, `R<round>-M<n>`, or `R<round>-L<n>`
2. severity
3. exact current location
4. reviewer opinion
5. concrete impact
6. precise correction
7. whether it is new, incomplete, or regressed

Uncertain matters go under **Questions**, not findings. The reviewer ends with
one explicit overall opinion:

- **Cleared** — safe as the implementation source of truth and no high
  blockers remain
- **Not cleared** — with the blocking reason

Wait for the reviewer result. Read it once; do not duplicate the review in the
main context.

### 2. Append Review

Append a concise but complete reviewer record before editing documents:

```markdown
## Round N - <exact model> - YYYY-MM-DD

### Review

#### Overall opinion

<reviewer conclusion>

#### Findings

| ID | Severity | Location | Reviewer opinion | Impact | Recommended correction |
|---|---|---|---|---|---|

#### Questions

| ID | Reviewer question |
|---|---|
```

Preserve every meaningful finding ID, severity, location, impact, and
recommendation. Summarize verbose prose; do not weaken the opinion.

### 3. Evaluate and fix

Evaluate every finding against the current documents, repository intent, and
primary sources. Assign one disposition:

- **Accepted** — fix it now
- **Rejected** — explain why it is not a defect
- **Deferred** — state the blocker and residual risk

Apply every accepted fix across all synchronized or dependent documents. Fix
the interface or rule that caused the issue, not only the quoted sentence.
Keep the requested scope and avoid production-grade expansion that the
documents do not require.

Validate the exact corrections with the smallest useful checks. Examples:

- schema metaschema and positive/negative instances
- JSON or YAML example parsing
- digest or canonicalization vectors
- balanced Markdown fences
- diagram/source terminology checks
- stale-term searches
- repository documentation tests

### 4. Append Response

Append the response below the same round:

```markdown
### Response

#### Overall response

<summary>

#### Findings

| ID | Disposition and fix |
|---|---|

#### Question resolutions

| ID | Resolution |
|---|---|

#### Validation

- <check and result>
```

Every reviewer finding and question must have one matching response row. Keep
rejected and deferred items visible.

## Continue or stop

After the response:

1. **Continue** when any high blocker remains.
2. **Continue** when accepted fixes changed a reviewed document, because the
   previous opinion predates those edits.
3. **Stop cleared** only when the latest reviewer opinion is **Cleared**, has no
   high findings, and the response made no material document edit.
4. **Stop at limit** after the configured maximum number of rounds, even when
   blockers remain.

When the limit is reached, append:

```markdown
## Final status

**Stop reason:** Maximum rounds reached.

**Unresolved high blockers:** <IDs or "none">
```

When cleared, append:

```markdown
## Final status

**Stop reason:** Reviewer cleared the documents with no high blockers.

**Cleared in round:** N
```

Report the stop reason, rounds completed, log path, unresolved high blockers,
and modified document paths.
