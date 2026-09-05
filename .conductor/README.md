# Conductor development

Local macOS workspaces keep using native uv/npm and the existing MariaDB services.
Their decksite script must pass the allocated `CONDUCTOR_PORT`. Cloud scripts do
not run on macOS and do not use Docker.

## Cloud startup and previews

The shared setup script runs `bash .conductor/setup.sh`. It syncs Python dependencies,
restores a prepared database, and builds JavaScript. Use the **decksite_cloud** run
script to start the app on port 5000 with Python auto-reload and no interactive
debugger. After changing JavaScript, run `npm run build` (or `npm run watch`).

**Enable port forwarding in the workspace's Ports panel.** Merely detecting port
5000 in the VM does not enable forwarding on the Mac. Open the forwarded entry for
5000; its Mac port can differ from 5000 and can change when reconnecting. A cloud
`http://127.0.0.1:5000` health check verifies the VM only, not the Mac tunnel.

An agent with RunLocalCommand can identify the actual mapping with this read-only
query on the Mac (substitute the current `CONDUCTOR_WORKSPACE_ID`):

```sh
sqlite3 -readonly "$HOME/Library/Application Support/com.conductor.app/conductor.db" \
  "SELECT local_port FROM port_forwards WHERE workspace_id = '<workspace-id>' AND remote_port = 5000 AND enabled = 1;"
```

Then verify `http://127.0.0.1:<local_port>/` from the Mac before sharing that link.
This database is an implementation detail; if its schema changes, use the Ports UI.
Leave the development server running after verification.

If the Ports toggle is unavailable, use `.conductor/preview-tunnel.py` on the Mac
to forward port 5000 through Conductor's existing SSH mapping for remote port 22.
A plain `ssh -f -N` tunnel is insufficient: VM restart/resume kills the database,
web server, and SSH connection. The supervisor reconnects, and its restricted SSH
command runs `.conductor/preview-ssh.sh` to restart MariaDB and decksite as needed.
The supervisor exits when Conductor closes the workspace's SSH listener.

Use a temporary key restricted to `127.0.0.1:5000` forwarding and a forced command
that runs `preview-ssh.sh` as the workspace user. For this Amazon Linux sandbox,
the authorized-key options are:

```text
restrict,port-forwarding,permitopen="127.0.0.1:5000",command="/usr/bin/sudo -u vercel-sandbox /bin/bash <workspace-path>/.conductor/preview-ssh.sh"
```

The sandbox's sshd may use `/root/.ssh/authorized_keys` (check `sshd -T`). Preserve
existing keys. Store the temporary private key as `id` on the Mac, together with
a `known_hosts` file containing the verified cloud SSH host key. Copy
`preview-tunnel.py` to that temporary directory and start it with:

```sh
python3 /tmp/<preview-directory>/preview-tunnel.py \
  --directory /tmp/<preview-directory> --ssh-port <Conductor-SSH-local-port> \
  --web-port <Mac-preview-port>
```

Launch the supervisor detached with logs saved in that directory, and record its
PID and the chosen Mac URL in `.context/pd-preview.json`. Stop it with
`kill "$(cat /tmp/<preview-directory>/supervisor.pid)"`. This is a temporary
fallback; the Ports panel remains the normal way to manage forwarding. The Mac
supervisor must be restarted after quitting Conductor or restarting the Mac.
Verify recovery by stopping the preview and its database, then checking that the
same Mac URL returns HTTP 200 without manually restarting either service.

## Database lifecycle

Cloud MariaDB runs as the workspace user on `127.0.0.1:3307`, with its data in
`.context/pd-cloud/mysql`. It does not modify `/var/lib/mysql` or fight a preexisting
service on 3306. Setup writes matching development credentials and database names
to gitignored `config.json`, disables issue reporting/Redis/Sentry, and verifies
deck data, card data, search suggestions, and the generated font. Search assets
live in `.context/pd-cloud` so a JavaScript build cannot remove them.

The snapshot contains decksite's sanitized dev data, Scryfall cards, empty prices,
pdlogs and test databases, a Whoosh index, search suggestions, the symbols font,
and the homepage's daily archetype summary (which is missing from the SQL dump).
It is a development dataset, not a complete copy of every production database.
No copied config files or credentials from the user's Mac go into the snapshot.

Setup downloads the `dev-db-snapshot` release's archive, manifest, and checksums
using authenticated `gh`. The release is a draft so building a snapshot does not
publish a release announcement. Cloud credentials need repository contents access
that can read this draft. Checksums, MariaDB major/minor, and architecture are
checked before extraction. A repeated setup reuses the workspace database;
it never refreshes or overwrites local edits. An incomplete or incompatible
database fails with an actionable error instead of starting a long SQL import.

The base cloud image should already have MariaDB **11.8**, uv, Node **24**/npm, gh,
zstd, pkg-config, and the MariaDB C development headers. Missing MariaDB packages
are installed with dnf on Amazon Linux. Package installation and a cold Python
dependency download may exceed the 1–2 minute target. Keep the image's dependencies
warm; database seeding belongs in the snapshot workflow, not an image boot hook.
Remove any old external boot hook that downloads/imports SQL when editing that
image configuration; these repository scripts do not rely on it.

Measured in the September 4, 2026 Amazon Linux cloud workspace: **46.8 seconds**
for a fresh GitHub snapshot download, checksum verification, database restore,
Python sync, npm install, and JavaScript build, plus **10.7 seconds** to start decksite and receive HTTP 200
(**57.5 seconds total**). This used the existing image's
toolchains/Python environment and a 1.46 GB archive. Network speed and missing
dependencies affect subsequent workspaces; this is a measurement, not a hard SLA.

## Refresh the snapshot

`.github/workflows/dev-db-snapshot.yml` builds weekly and on demand after merging.
It installs matching native MariaDB, imports the public sanitized SQL, initializes
cards, generates assets and homepage summaries, shuts down cleanly, and verifies
a fresh restore and real HTTP responses from core pages before
uploading the archive. Rebuilding takes several minutes, outside workspace startup.
Concurrent refreshes are serialized. If startup happens during asset replacement,
a checksum/download failure is safe: retry setup after the workflow finishes.

To build manually in a fresh Linux checkout with dependencies installed:

```sh
python3 .conductor/cloud.py build-snapshot
```

The builder refuses an existing `.context/pd-cloud`. For offline restore testing,
set `PD_CLOUD_SNAPSHOT_DIR` to the absolute path of `.context/pd-cloud-artifacts`.
For snapshot builds, `PD_DEV_SQL` can point to a previously downloaded sanitized
`dev-db.sql.gz`. Normal workspace setup never invokes the snapshot builder.

Shared run-script changes appear on the Mac after merging to the default branch;
cloud setup uses the branch used to create the workspace. Machine-local settings
can override these shared settings, so check `.conductor/settings.local.toml` if
Conductor runs an unexpected command.
