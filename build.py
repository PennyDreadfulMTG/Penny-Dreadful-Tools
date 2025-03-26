import subprocess
import sys

ON_WINDOWS = sys.platform == 'win32'


def build() -> None:
    buildpy()
    buildjs()
    buildfonts()

def buildpy() -> None:
    print('>>>> Installing Requirements')
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pipenv'])
    subprocess.check_call(['pipenv', 'sync', '--dev'])


def buildjs() -> None:
    print('>>>> Installing node modules')
    subprocess.check_call(['npm', 'install'], shell=ON_WINDOWS)
    print('>>>> Building javascript')
    subprocess.check_call(['npm', 'run-script', 'build'], shell=ON_WINDOWS)


def buildfonts() -> None:
    print('>>>> Enabling lfs if necessary')
    subprocess.check_call(['git', 'lfs', 'install'])
    print('>>>> Getting font binaries')
    subprocess.check_call(['git', 'lfs', 'pull'])
    print('>>>> Building local font subset')
    subprocess.check_call(['pipenv', 'run', 'python', 'run.py', 'maintenance', 'fonts'])


if __name__ == '__main__':
    build()
