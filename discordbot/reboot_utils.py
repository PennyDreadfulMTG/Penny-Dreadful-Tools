import asyncio

REBOOT_KEY = 'discordbot:do_reboot'
REBOOT_CHANNEL_KEY = 'discordbot:reboot_channel_id'
REBOOT_COMPLETE_CHANNEL_KEY = 'discordbot:reboot_complete_channel_id'
SHUTDOWN_TIMEOUT_SECONDS = 10


class RebootUpdateError(Exception):
    def __init__(self, command: str, returncode: int | None, output: str) -> None:
        self.command = command
        self.returncode = returncode
        self.output = output.strip() or '(no output)'
        status = f'exited with status {returncode}' if returncode is not None else 'could not be started'
        super().__init__(f'{command} {status}')

    @property
    def diagnostic(self) -> str:
        return f'{self}: {self.output}'


async def update() -> RebootUpdateError | None:
    commands = [
        ('git pull', ('git', 'pull')),
        ('uv sync', ('uv', 'sync', '--frozen')),
    ]
    for display, command in commands:
        try:
            returncode, output = await run_command(*command)
        except Exception as e:
            return RebootUpdateError(display, None, str(e))
        if returncode != 0:
            return RebootUpdateError(display, returncode, output)
    return None


async def run_command(*command: str) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    return process.returncode or 0, stdout.decode(errors='replace')
