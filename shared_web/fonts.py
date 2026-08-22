import subprocess


def regenerate_symbols_font() -> None:
    # Font generation takes too long to do while handling a request, so leave it to
    # a detached process that can outlive the web worker that started it.
    subprocess.Popen(
        ['uv', 'run', '--frozen', 'python', 'run.py', 'maintenance', 'fonts'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
