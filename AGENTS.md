# Working in this repo

## Merging pull requests

To merge a PR, comment `@mergifyio queue` on it (for example `gh pr comment <number> --body "@mergifyio queue"`).
Mergify then merges it once the mypy, lint, test and jslint checks pass.

Do not use the "merge when ready" label. It is a leftover from an old CI setup and Mergify ignores it.
