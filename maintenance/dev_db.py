import gzip
import subprocess

from shared import configuration


def run() -> None:
    """Make a 'safe' (no personal info) copy of the current prod db for download by devs."""
    host = configuration.get('mysql_host')
    port = configuration.get('mysql_port')
    usr = configuration.get('mysql_user')
    pwd = configuration.get('mysql_passwd')
    db = configuration.get('decksite_database')
    base_command = ['mysqldump', '-h', host, '-P', str(port), '-u', usr, f'-p{pwd}']
    structure = subprocess.check_output(base_command + ['--no-data', db])
    data = subprocess.check_output(base_command + ['--ignore-table=person_note', db])
    with gzip.open('shared_web/static/dev-db.sql.gz', 'wb') as f:
        f.write(structure)
        f.write(data)
