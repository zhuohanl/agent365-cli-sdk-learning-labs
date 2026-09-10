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

Run each experiment independently. A result from one selected GCP agent does
not authorize another write or prove behavior for another provider.

## Demos

Run lifecycle demos in this order when they use the same companion:

1. `demos/01-add-companion/demo.http`
2. `demos/02-rename-companion/demo.http`
3. `demos/03-delete-companion/demo.http`

Delete is last because it removes the Registration required by the rename
demo. Each demo remains gated and can instead use a different explicitly
approved disposable agent selected through `.env`.

## Shared local configuration

Keep one ignored `.env` beside this README. Group variables under comments for
shared authentication, each experiment, and the demos. Never commit the file,
copy it into a child folder, or save tokens and provider credentials as
evidence.
