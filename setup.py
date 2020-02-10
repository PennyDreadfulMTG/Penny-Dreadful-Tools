import setuptools

with open('README.md', 'r') as fh:
    DESC = fh.read()

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
)
