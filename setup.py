import setuptools

with open('README.rst', 'r') as f:
    long_description = f.read()

with open('schwab/version.py', 'r') as f:
    '''Version looks like `version = '1.2.3'`'''
    version = [s.strip() for s in f.read().strip().split('=')][1]
    version = version[1:-1]

# The interactive login flow runs a local HTTPS callback server in a separate
# process. Nothing else needs any of this, and a process which loads its token
# from a file should not carry a web framework.
LOGIN_REQUIRES = [
    'flask',
    'multiprocess',
    'psutil',
]

# contrib.orders formats the code it generates.
CODEGEN_REQUIRES = [
    'autopep8',
]

setuptools.setup(
    name='schwab-py',
    version=version,
    # Authorship stays with the original author, who wrote essentially all of
    # this. His contact details are deliberately not carried over: support for
    # this fork should not land in his inbox.
    author='Alex Golec',
    maintainer='Hu1kSmash',
    description=('Unofficial API wrapper for the Schwab HTTP API '
                 '(maintained fork of alexgolec/schwab-py)'),
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url='https://github.com/Hu1kSmash/schwab-py',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Development Status :: 1 - Planning',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Topic :: Office/Business :: Financial :: Investment',
    ],
    python_requires='>=3.10',
    install_requires=[
        'authlib>=1.8',
        'httpx2>=2.12.0',
        'websockets>=14.0'
    ],
    extras_require={
        'login': LOGIN_REQUIRES,
        'codegen': CODEGEN_REQUIRES,
        # Composed rather than restated. The suite really starts flask servers
        # through multiprocess, so dev depends on the extras; listing them
        # twice meant adding a package to an extra and forgetting dev produced
        # a green local run against a stale virtualenv and a red CI, failing in
        # auth tests rather than anywhere near the change.
        'dev': LOGIN_REQUIRES + CODEGEN_REQUIRES + [
            'callee',
            'colorama',
            'coverage',
            'pytest',
            'requests',
            'pytz',
            'setuptools',
            'sphinx_rtd_theme',
            'twine',
            'wheel',
        ]
    },
    keywords='finance trading equities bonds options research',
    project_urls={
        'Documentation': 'https://github.com/Hu1kSmash/schwab-py/blob/main/docs/index.rst',
        'Source': 'https://github.com/Hu1kSmash/schwab-py',
        'Tracker': 'https://github.com/Hu1kSmash/schwab-py/issues',
        'Upstream': 'https://github.com/alexgolec/schwab-py',
    },
    license='MIT',
    scripts=[
        'bin/schwab-order-codegen.py',
        'bin/schwab-generate-token.py',
    ],
)

