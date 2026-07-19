# Security policy

## Supported versions

Before the first tagged release, security fixes are applied to the current `main` branch. After a
release is tagged, the latest release and `main` are supported.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/ownasquare/dataset-foundry/security/advisories/new).
If that option is temporarily unavailable, use the private contact method on the maintainer's
GitHub profile rather than opening a public issue.

Include a minimal reproduction, affected version, impact, and any suggested mitigation. Do not
attach provider keys, customer training data, private prompts, databases, or generated artifacts.

## Security boundaries

- Dataset Foundry binds to loopback by default.
- Live provider use requires explicit data-transfer consent and server-side credentials.
- Provider credentials are never returned by the API or placed in the browser bundle.
- Upload size, row count, format, and schema are validated before persistence.
- Exports are written beneath the configured artifact directory with generated identifiers.
- Offline mode makes no network calls and is the default for demos and automated tests.

When binding to a non-loopback interface, configure an API key and terminate TLS at a trusted
reverse proxy. Treat imported seeds, provider prompts, candidate text, and exports as sensitive
customer data.
