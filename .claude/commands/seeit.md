Start a browser preview of the current workspace and give the user the actual,
verified URL they can open. Read `AGENTS.md` and `.conductor/README.md` first and
follow their preview requirements. Use `/` unless the conversation identifies a
more relevant path.

Determine the environment from `CONDUCTOR_IS_LOCAL`:

- Locally, use the workspace's native MariaDB and `CONDUCTOR_PORT`. Reuse a
  healthy server on that port; otherwise start decksite as a long-lived process
  with:

  ```bash
  uv run --frozen python -c 'import os; from decksite import main; main.init(port=int(os.environ["CONDUCTOR_PORT"]))'
  ```

  The browser URL is `http://127.0.0.1:$CONDUCTOR_PORT/<path>`.

- In a cloud workspace, run `bash .conductor/setup.sh`, which starts/verifies the
  workspace database without importing SQL. Reuse a healthy decksite process on
  port 5000; otherwise start `bash .conductor/decksite-cloud.sh` as a long-lived
  process. Wait for the relevant VM URL to return HTTP 200.

  Check `.context/pd-preview.json` for an existing supervised preview first. If
  none exists, use Conductor's `RunLocalCommand` tool to query the Mac's enabled
  forwarding entry. Substitute the literal value of `CONDUCTOR_WORKSPACE_ID` in
  this read-only command before sending it to the Mac:

  ```bash
  sqlite3 -readonly "$HOME/Library/Application Support/com.conductor.app/conductor.db" "SELECT local_port FROM port_forwards WHERE workspace_id = '<workspace-id>' AND remote_port = 5000 AND enabled = 1;"
  ```

  Verify `http://127.0.0.1:<local-port>/<path>` from the Mac with
  `RunLocalCommand`, then give that exact URL to the user. Never present the
  cloud VM's `127.0.0.1:5000` as a user-accessible link. If no enabled mapping is
  returned, ask the user to enable detected port 5000 in Conductor's Ports
  popover; if `RunLocalCommand` is unavailable, explain that the Mac-side port
  cannot be discovered or verified from the cloud VM.

Build JavaScript first with `npm run build` when the current changes affect
JavaScript. Exercise the relevant page and assets in a browser, report what was
verified, and leave the development server running.
