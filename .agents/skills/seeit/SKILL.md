---
name: seeit
description: Start or reuse the Penny Dreadful development site and database, browser-check the relevant page, and return the exact Conductor-aware URL the user can open. Use for preview, dev-server, browser-link, and "see it" requests.
---

# See It

Prepare a browser preview for the current workspace. Use `/` unless the request
identifies a more relevant path. Read `.conductor/README.md` before using its SSH
fallback.

## Start and verify decksite

Build JavaScript with `npm run build` first when the current changes affect it.

- With `CONDUCTOR_IS_LOCAL=1`, require `CONDUCTOR_PORT`. Reuse decksite if the
  relevant URL is healthy; otherwise start this as a long-lived process against
  the user's existing native MariaDB:

  ```bash
  uv run --frozen python -c 'import os; from decksite import main; main.init(port=int(os.environ["CONDUCTOR_PORT"]))'
  ```

  Verify and return `http://127.0.0.1:$CONDUCTOR_PORT/<path>`.

- With `CONDUCTOR_IS_LOCAL=0`, run `bash .conductor/setup.sh`. It restores or
  verifies the prepared database without importing SQL. Reuse a healthy server
  on port 5000; otherwise start `bash .conductor/decksite-cloud.sh` as a
  long-lived process. Wait for `http://127.0.0.1:5000/<path>` to return HTTP 200,
  then browser-check the page and relevant assets inside the VM.

Leave the development server running.

## Resolve the user's cloud URL

The VM URL proves decksite is healthy but is not necessarily the Mac URL. Check
`.context/pd-preview.json` for an existing supervised preview. Otherwise use
Conductor's `RunLocalCommand` tool. In Codex code mode this tool can be lazily
exposed through the tool runner: search its `ALL_TOOLS` catalog for
`RunLocalCommand`, then call the returned nested tool (currently
`mcp__conductor__RunLocalCommand`). Do not infer that it is unavailable from an
abbreviated initial tool list.

Take the literal UUID from `CONDUCTOR_WORKSPACE_ID` and substitute it for
`<workspace-id>` in this read-only Mac command:

```bash
sqlite3 -readonly "$HOME/Library/Application Support/com.conductor.app/conductor.db" "SELECT local_port FROM port_forwards WHERE workspace_id = '<workspace-id>' AND remote_port = 5000 AND enabled = 1;"
```

When it returns a port, use `RunLocalCommand` again to request
`http://127.0.0.1:<local-port>/<path>`. Return that exact URL only after the Mac
request succeeds.

No row means forwarding is not enabled; it does not mean `RunLocalCommand` is
unavailable. Confirm the state with this read-only query:

```bash
sqlite3 -readonly -header -column "$HOME/Library/Application Support/com.conductor.app/conductor.db" "SELECT auto_forward_enabled, port_forwarding_enabled FROM workspaces WHERE id = '<workspace-id>';"
```

If `port_forwarding_enabled` is `0`, ask the user to enable detected port 5000
in the workspace's Ports popover, then repeat the lookup and Mac HTTP check. If
the Ports control is unavailable, follow the supervised SSH fallback in
`.conductor/README.md`, record its URL in `.context/pd-preview.json`, and verify
recovery as described there.

Never present the cloud VM's `127.0.0.1:5000` as the user's forwarded URL.
