---
name: committed-fleet-environment-setup
description: Guide, resume, verify, or report committed-fleet platform environment setup. Use for environment readiness, human portal gates, lifecycle review, canonical local binding initialization, or implementation handoff.
compatibility: Repository skill for GitHub Copilot and Codex; Claude Code uses the matching project command.
---

# Committed Fleet Environment Setup

This skill is the agent entry point for the committed-fleet environment
baseline.

Default to a **guided walkthrough**. Ask one plain question at a time. Do not
generate a shell wizard unless the user explicitly requests a script.

## 1. Orient

Read these files first:

1. `CONTEXT.md`
2. `docs/platform_environment_readiness.md`
3. `infrastructure/environments/templates/committed-fleet/environment-readiness-checklist.md`

If the task is ticket work, refresh issue #8 before changing its state.

**Done when:** you can name every pending human gate and every implementation
proof without treating portal access as readiness.

## 2. Select the branch

### Guided human setup

Use this branch for portal, account, licence, consent, payment, trial, and
secret-custody actions.

In an interactive session:

1. Start with the first pending row, or the row the user names.
2. Explain why the action is needed in one short paragraph.
3. Ask one question for each missing human decision, with the recommended
   option first. One decision can resolve several implementation fields; do
   not turn derived values or fixed defaults into separate questions.
4. Give the current portal navigation path.
5. Ask the user to report only the observable, non-secret result.
6. Record the result before moving to the next row.

For each human action, supply:

- purpose
- portal and navigation path
- least-privilege role
- safe value or selection rule
- external secret-store destination, when applicable
- observable success condition
- rollback or cleanup
- non-secret fact to return

When the visible portal differs from the documented path, use current
first-party documentation or ask what options are visible. Treat the visible
portal as evidence. Never invent a menu.

In a non-interactive coding-agent session, write or update the resumable
checklist. Mark each unresolved portal action as `human step pending`, name its
owner, and stop at the human boundary. Do not claim that the action completed.

**Done when:** each human row is `complete`, `pending`, or `unavailable`, with
an owner and an observable next test.

### Implementation automation

Use this branch only when the user asks for implementation work.

Read the **Implementation automation handoffs** table in
`environment-readiness-checklist.md`, then follow the ownership rules in
`docs/adr/0001-platform-first-polyglot-monorepo.md`:

- reusable platform infrastructure:
  `platforms/<family>/<runtime>/infrastructure/`
- prerequisite checks and data loaders:
  `platforms/<family>/<runtime>/test-support/`
- cross-platform composition:
  `infrastructure/environments/`
- agent-local non-secret declarations:
  `platforms/<family>/<runtime>/agents/agent-NN/config/`

Perform CLI, API, infrastructure-as-code, resource creation, and smoke tests
in implementation. Do not assign these actions to the human.

**Done when:** the applicable proof is reproducible, harmless, least privilege,
and has a cleanup path.

### Expiry or lifecycle review

Read:

- `docs/research/platform_environment_expiry_rules.md`
- `infrastructure/environments/templates/committed-fleet/commercial-controls.md`

Record generic policy rules in tracked files. Record exact subscription dates,
credit balances, selected plan names, warning dates, and environment
identifiers only in the ignored local binding record.

**Done when:** every trial, credit, paid account, and inactivity-based
environment has an owner, a next deadline or maintenance cadence, and a
cleanup action.

### Residency or unavailable capability

Read only the applicable file:

- residency:
  `infrastructure/environments/templates/committed-fleet/outside-country-register.md`
- product limits:
  `infrastructure/environments/templates/committed-fleet/unavailable-capabilities.md`

Use the split-plane rule. Content stores stay in the required country. An
off-country runtime can process content but cannot persist corpus content.

**Done when:** every outside-country component or unavailable capability has a
consequence and an affected agent or implementation owner.

## 3. Record safely

Start from the repository root:

```powershell
pwsh -NoProfile -File `
  .\infrastructure\environments\scripts\Initialize-CommittedFleetBinding.ps1
```

This command creates the canonical ignored binding or adds missing structure
from `manual-binding-record.example.yaml`. It preserves every existing value.
Run `Test-CommittedFleetBinding.ps1` in the same script directory when you need
exact missing or incompatible field paths. Its output contains paths, not
values.

Treat this binding as reusable environment state. Reuse an existing approved
value across tickets. Before each platform write, validate the active context
against that state; do not repeat the guided walkthrough for unchanged values.
Resolve fixed defaults, stable names and permitted current-principal details
without asking the human.

`infrastructure/environments/templates/committed-fleet/committed-fleet.binding.local.yaml`

This file is ignored by Git.

For an isolated ticket worktree, follow **Reuse from an isolated ticket
worktree** in
`infrastructure/environments/templates/committed-fleet/README.md`. That path
updates the primary clone's canonical binding directly and uses the same file
through `COMMITTED_FLEET_BINDING` or the implementation command's
`-BindingPath` parameter.

Tracked records contain:

- readiness state
- capability class
- logical secret alias
- generic region class
- proof description
- cost, quota, expiry, and cleanup rule

The canonical ignored local binding record contains:

- exact expiry dates and balances
- environment references and resolved endpoints
- selected plan and account state
- local evidence references

Secrets go directly to the approved external store. Record only their logical
aliases.

Before publishing, scan tracked changes for credentials, environment
identifiers, local paths, customer details, country names, and project
codenames.

## 4. Publish the state

When working ticket #8:

1. Refresh issue #8 before posting.
2. Report complete and pending human gates separately.
3. Report implementation proofs separately.
4. Keep the issue open while any required human gate or proof is incomplete.
5. Update map #4 only when ticket #8 resolves.

Use these readiness meanings:

- `ready`: access and the minimum required capability were tested
- `provisioned`: created and smoke-tested in this work
- `human step pending`: a precise owner action remains
- `unavailable`: an exact product, licence, region, or technical blocker is
  recorded

**Done when:** the repository and ticket show the same public-safe state, and
no environment is marked `ready` without an implementation proof.
