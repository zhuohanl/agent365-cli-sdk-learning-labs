# Lab 20 HTTP experiments and demos

This directory separates evidence-producing experiments from repeatable
lifecycle demonstrations.

All request files select their GCP agent and related Agent 365 objects through
the single ignored `.env` in the Lab 20 root. REST Client 0.25.1 searches parent
directories for `.env`, so do not copy credentials into the child folders.

## Experiments

| Folder | Question | Evidence |
| --- | --- | --- |
| `experiments/01-package-registration-lookup` | Can a Registry Sync Package ID or provider source ID address an Agent Registration? | `evidence/experiments/01-package-registration-lookup` |
| `experiments/02-provider-source-registration-create` | What happens when the provider-native source ID is submitted directly as a new Registration source without identity fields? | `evidence/experiments/02-provider-source-registration-create` |
| `experiments/03-companion-source-registration-create` | Can a distinct companion source ID be registered with a Blueprint and Agent Identity while leaving the Registry Sync Package unchanged? | `evidence/experiments/03-companion-source-registration-create` |
| `experiments/04-source-id-stability` | Which source, connection, and Package identifiers survive sync, rename, and connection recreation? | `evidence/experiments/04-source-id-stability` |
| `experiments/05-enterprise-interaction-history` | What interaction-history behavior is exposed for an enterprise agent? | `evidence/experiments/05-enterprise-interaction-history` |
| `experiments/06-package-blueprint-lookup` | Given a Package ID, which Agent Identity and parent Blueprint does it resolve to? | `evidence/experiments/06-package-blueprint-lookup` |

Run each experiment independently. A result from one selected GCP agent does
not authorize another write or prove behavior for another provider.

Save every experiment result as JSON under its specified ignored evidence
directory. Raw JSON response bodies can be saved directly. When a step has no
body, or only a safe status/error summary should be retained, use:

```json
{
  "step": "<request-or-manual-checkpoint-name>",
  "observedAt": "<UTC-timestamp>",
  "httpStatus": 204,
  "outcome": "<supported|unsupported|unavailable|permission-denied|inconclusive>",
  "body": null,
  "safeNotes": "<non-identifying-summary>"
}
```

Do not save authentication responses. Do not put tokens, tenant values,
identifiers, endpoints, or identifying screenshots in tracked files.

## Demos

Run lifecycle demos in this order when they use the same companion:

1. `demos/01-add-companion/demo.http`
2. `demos/02-rename-companion/demo.http`
3. `demos/03-delete-companion/demo.http`

Delete is last because it removes the Registration required by the rename
demo. Each demo remains gated and can instead use a different explicitly
approved disposable agent selected through `.env`.

Before demo 01, provide the exact GCP Package display name and the standing
dedicated-onboarding policy metadata:

```dotenv
A365_DEMO_TARGET_NAME=<exact-GCP-package-display-name>
A365_DEMO_GROUPING_POLICY_VERSION=<approved-standing-policy-version>
A365_DEMO_APPROVAL_REFERENCE=<approved-standing-policy-reference>
```

After Package discovery, the helper generates a deterministic dedicated
assignment and `A365_DEMO_BLUEPRINT_GROUP`. Reconcile that exact group against
protected local mapping. Set `A365_DEMO_BLUEPRINT_OBJECT_ID` only when the
mapping identifies its existing Blueprint; otherwise leave it empty. Demo 01
then follows the Experiment 03 order: Blueprint and principal, Agent Identity,
companion Registration, Registration readback, and independent reads of the
original and companion Packages.

The `demos/01-add-companion/prepare_demo.py` helper derives Package and source
values from saved read-only responses, generates the dedicated assignment, and
encodes the returned Registration ID for URL-path use. After the creates, it
saves the ignored durable mapping and generated IDs used by demos 02 and 03.
It never obtains a token, calls Microsoft Graph, or prints identifiers.

Each lifecycle demo starts with the explicit two-request authentication used
by Experiment 1: request a device code, complete browser sign-in, and exchange
the code for one short-lived token. This avoids embedding tenant identifiers in
tracked files and avoids multiple hidden sign-in dialogs.

## Shared local configuration

Keep one ignored `.env` beside this README. Group variables under comments for
shared authentication, each experiment, and the demos. Never commit the file,
copy it into a child folder, or save tokens and provider credentials as
evidence.
