from pathlib import Path

from setuptools import setup, find_packages

long_description = (Path(__file__).parent / 'README.md').read_text()

setup(
    name='tuck',
    version='0.2.4',
    url='https://github.com/PeterJCLaw/tuck',
    project_urls={
        'Issue tracker': 'https://github.com/PeterJCLaw/tuck/issues',
    },
    description="Semi-automated Python formatting.",
    long_description=long_description,
    long_description_content_type='text/markdown',

    package_data={'tuck': ['py.typed']},
    packages=find_packages(exclude=['tests']),

    author="Peter Law",
    author_email="PeterJCLaw@gmail.com",

    license='Apache 2.0',

    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Topic :: Software Development',
    ],

    install_requires=(
        'asttokens >=2, <3',
    ),
    python_requires='>=3.7',
)
