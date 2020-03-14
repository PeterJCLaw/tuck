import os.path

from setuptools import setup

my_dir = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(my_dir, 'README.md')) as f:
    long_description = f.read()

setup(
    name='tuck',
    version='0.0.1',
    url='https://github.com/PeterJCLaw/tuck',
    description="Semi-automated Python formatting.",
    long_description=long_description,
    long_description_content_type='text/markdown',

    packages=[],

    author="Peter Law",
    author_email="PeterJCLaw@gmail.com",

    classifiers=(
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development',
    ),

    install_requires=(
        'asttokens',
    ),
)
