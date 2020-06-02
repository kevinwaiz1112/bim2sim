from setuptools import setup, find_packages

from os import path
parent_dir = path.abspath(path.dirname(path.dirname(__file__)))
with open(path.join(parent_dir, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='bim2sim',
    version='0.1.dev0',
    description='Create simulation models from IFC files',
    license="???",
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='BIM2SIM',
    author_email='CWarnecke@rom-technik.de',
    url="https://www.ebc.eonerc.rwth-aachen.de/go/id/qxtv",
    packages=find_packages() + ['bim2sim.assets'],
    include_package_data=True,
    python_requires='>=3.6.0',
    install_requires=[
        'docopt', 'numpy', 'python-dateutil',
        'mako', 'networkx>=2.2', 'pint'
    ],  # external packages as dependencies
    extras_require={
        'manual_install': ['ifcopenshell>=0.6'],
        'plotting': ['matplotlib'],
    },
    entry_points={
        'console_scripts': [
            'bim2sim = bim2sim:main',
        ],
    }
)
