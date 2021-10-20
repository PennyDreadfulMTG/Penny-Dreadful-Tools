import sys
import subprocess

ON_WINDOWS = sys.platform == 'win32'


def build() -> None:
    buildpy()
    buildjs()

def buildpy() -> None:
    print('>>>> Installing Requirements')
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pipenv'])
    subprocess.check_call(['pipenv', 'sync', '--dev'])
    if sys.prefix == sys.base_prefix:
        subprocess.check_call([sys.executable, '-m', 'pipenv', 'install', '--system', '--dev'])

def buildjs() -> None:
    print('>>>> Installing node modules')
    subprocess.check_call(['npm', 'install'], shell=ON_WINDOWS)
    print('>>>> Building javascript')
    subprocess.check_call(['npm', 'run-script', 'build'], shell=ON_WINDOWS)


if __name__ == '__main__':
    build()
