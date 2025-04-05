import gzip
import subprocess

from shared import configuration
from shared.pd_exception import InvalidArgumentException, OperationalException

DAILY = True

def run() -> None:
    """Make a 'safe' (no personal info) copy of the current prod db for download by devs."""
    # Although we have a mysql_port config item I don't use it here so this will use a socket.
    # If we are ever in a situation where we must use TCP to connect to the db on a nonstandard port this may fail.
    host = configuration.mysql_host.value
    usr = configuration.mysql_user.value
    pwd = configuration.mysql_passwd.value
    db = configuration.get_str('decksite_database')
    if not (host or usr or pwd or db):
        safe_pwd = 'PRESENT' if pwd else 'MISSING'
        raise InvalidArgumentException(f'Unable to dump dev db with {host} {usr} pwd:{safe_pwd} {db}')
    base_command = ['mariadb-dump', '-h', host, '-u', usr, f'-p{pwd}']
    try:
        structure = subprocess.check_output(base_command + ['--no-data', db])
        data = subprocess.check_output(base_command + [f'--ignore-table={db}.person_note', db])
        with gzip.open('shared_web/static/dev-db.sql.gz', 'wb') as f:
            f.write(structure)
            f.write(data)
    except subprocess.CalledProcessError:
        # Avoid logging the password to perf-reports by raising a different exception. See #6930.
        raise OperationalException('Failed to backup dev db')
