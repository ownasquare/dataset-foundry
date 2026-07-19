## What changed

Describe the user-visible outcome and why this is the smallest useful change.

## Proof

- [ ] Focused tests cover the changed behavior and failure path.
- [ ] `make check` passes.
- [ ] `make benchmark-ci` passes when generation/quality/export behavior changed.
- [ ] Playwright E2E passes when a user workflow changed.
- [ ] Cypress was used only for React component tests.
- [ ] Offline, live-provider, browser, package, container, hosted, and deployed proof are reported separately.

## Safety and compatibility

- [ ] No credential, customer seed, private prompt, database, or generated artifact is included.
- [ ] Provider selection never silently falls back.
- [ ] Schema, migration, privacy, cost, and immutable-export impacts are documented.
- [ ] User, contributor, API, or operations docs were updated where needed.
