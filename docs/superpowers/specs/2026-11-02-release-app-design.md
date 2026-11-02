# Dedicated Release Please identity

The user requested automatic checks for release proposals without the extra
workflow-approval click. Main protection and the maintainer's release merge stay
the publication gate. This extends the existing official Release Please workflow.

## Approach

Use a private GitHub App installed only on `brunofelixns/mealie-mcp-server`.
Compared with a repository-scoped PAT, installation tokens avoid a personal user
identity and are generated per job and revoked afterwards. The App needs only
Contents write (version branch/files) and Pull Requests write (proposal and labels).
Metadata read is mandatory. GitHub's labels API accepts Pull Requests write, so
Issues write is unnecessary. No Actions, Packages, Workflows or Administration
permission is requested for this App, and it gets no main-protection bypass.

Store the public client ID in `RELEASE_PLEASE_APP_CLIENT_ID` and the private key in
the Actions secret `RELEASE_PLEASE_APP_PRIVATE_KEY`. The pinned official
`actions/create-github-app-token` action requests only the current repository and
those two write permissions. Verify the token's installation-repository listing
before handing it to the official Release Please CLI. Missing credentials or an
unexpected repository scope fail visibly; there is no default-token fallback.

Only proposal maintenance uses the App token. Existing merged-release creation
and exact-tag dispatch use GITHUB_TOKEN; GHCR keeps its existing separate token.
The App token is not a job-wide environment variable and its key never belongs in
Git, application containers or evidence artifacts. Node24 stays inside this
Release Please CI workflow. Python, tests and builds stay in the Linux Dev Container.

## Activation and evidence

Prepare and test the workflow through a protected PR. Registration was blocked by
automatic approval review pending explicit approval of the persistent write scope;
do not retry registration or install the App until that approval arrives. After
approval, register the reduced scope, install on only the named repository, store
the key securely, and merge the configuration PR. Confirm a subsequent release
proposal update starts native pull_request checks without an approval call. Leave
the release PR open for the maintainer.
