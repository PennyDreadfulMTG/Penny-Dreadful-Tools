"""Mac-side SSH supervisor for one Conductor workspace; no extra dependencies.

Use a key whose forced command is preview-ssh.sh, restricted to port 5000.
Exit when Conductor closes this workspace's SSH listener. Otherwise reconnect
after a VM restart; the forced command also restores MariaDB and decksite.
"""
import argparse
import fcntl
import os
import signal
import socket
import subprocess
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--ssh-port', required=True, type=int)
    parser.add_argument('--web-port', required=True, type=int)
    args = parser.parse_args()
    directory = args.directory.resolve()
    child = None

    def stop(_signum: int, _frame: object) -> None:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=15)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with (directory / 'supervisor.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        (directory / 'supervisor.pid').write_text(str(os.getpid()))
        while True:
            try:
                with socket.create_connection(('127.0.0.1', args.ssh_port), timeout=5):
                    pass
            except OSError:
                # Don't keep a closed/archived workspace alive or reconnect forever
                # after the user quits Conductor.
                return
            child = subprocess.Popen([
                'ssh', '-T', '-i', str(directory / 'id'),
                '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                '-o', 'ExitOnForwardFailure=yes', '-o', 'ConnectTimeout=10',
                '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
                '-o', 'StrictHostKeyChecking=yes',
                '-o', f'UserKnownHostsFile={directory / "known_hosts"}',
                '-p', str(args.ssh_port),
                '-L', f'127.0.0.1:{args.web_port}:127.0.0.1:5000',
                'root@127.0.0.1',
            ], stdin=subprocess.DEVNULL)
            child.wait()
            time.sleep(3)


if __name__ == '__main__':
    main()
