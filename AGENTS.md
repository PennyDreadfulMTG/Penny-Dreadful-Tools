# Working in this repo

## Merging pull requests

To merge a PR, comment `@mergifyio queue` on it (for example `gh pr comment <number> --body "@mergifyio queue"`).
Mergify then merges it once the mypy, lint, test and jslint checks pass.

Do not use the "merge when ready" label. It is a leftover from an old CI setup and Mergify ignores it.

## Development previews

- Use native uv/npm and MariaDB; do not use Docker.
- In local Conductor workspaces, use the repository's local decksite run script
  and its allocated `CONDUCTOR_PORT`.
- In cloud workspaces (`CONDUCTOR_IS_LOCAL=0`), use `bash .conductor/setup.sh`
  and `bash .conductor/decksite-cloud.sh`. See `.conductor/README.md` for snapshot
  preparation and troubleshooting. Do not import SQL during workspace setup.
- For UI work, start the development server, verify the relevant page and assets,
  and leave it running. Build JavaScript changes with `npm run build`.
- Give the actual forwarded browser URL. Cloud port 5000 is not necessarily Mac
  port 5000. Port detection is separate from enabling forwarding in Conductor's
  Ports panel. Verify from the Mac with RunLocalCommand when available.
  Check `.context/pd-preview.json` for an existing temporary SSH preview tunnel.
