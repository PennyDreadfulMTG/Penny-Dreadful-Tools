import os

import setuptools

with open('README.md', 'r') as fh:
    DESC = fh.read()

REQ_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'requirements.txt')
INSTALL_REQUIRES = []
if os.path.isfile(REQ_PATH):
    with open(REQ_PATH) as f:
        INSTALL_REQUIRES = f.read().splitlines()

setuptools.setup(
    name='Penny Dreadful Tools',
    version='0.0.1',
    author='The Penny Dreadful Team',
    description='',
    long_description=DESC,
    long_description_content_type='text/markdown',
    url='https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
    install_requires=INSTALL_REQUIRES,
)
