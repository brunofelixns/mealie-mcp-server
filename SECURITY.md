# Security policy

## Supported versions

Security fixes target the latest published Python release of mealie-mcp-server.
Upgrade to that release before reporting an issue when possible. Older releases
and the original upstream implementation do not receive fixes in this repository.

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/brunofelixns/mealie-mcp-server/security/advisories/new).
Do not open a public issue or pull request with exploit details before a fix and
disclosure have been coordinated. If the private reporting form is unavailable,
request a private contact from [the maintainer](https://github.com/brunofelixns)
without including vulnerability details in a public message.

Include the affected version or image digest, transport (stdio or HTTP), relevant
configuration with secrets removed, reproduction steps using disposable data,
expected and observed behavior, and impact. Never include tokens, real recipes,
personal data, or signed URLs. A minimal example against a disposable local Mealie
instance is preferred; do not test against other people's deployments.

The maintainer will assess the report and coordinate a fix and disclosure through
the private advisory. This is a volunteer project; response and fix times are not
guaranteed. If a credential has leaked, revoke or rotate it immediately rather
than waiting for a project release.

## Deployment guidance

Follow the [HTTP deployment guide](docs/http-deployment.md), keep credentials out
of Git and logs, and review [CI and release evidence](docs/ci.md) for the image you
deploy. Automated scans and signed provenance do not guarantee an absence of
vulnerabilities. Report ordinary bugs using the public issue templates.
