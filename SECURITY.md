# Security policy

## Supported versions

Security fixes are applied to the current `main` branch and the latest tagged release.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to the repository owner. Include a minimal
reproduction, affected version, impact, and any suggested mitigation. Do not attach provider keys,
customer training data, private prompts, or generated artifacts.

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

