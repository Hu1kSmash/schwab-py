import setuptools

with open('README.rst', 'r') as f:
    long_description = f.read()

with open('schwab/version.py', 'r') as f:
    '''Version looks like `version = '1.2.3'`'''
    version = [s.strip() for s in f.read().strip().split('=')][1]
    version = version[1:-1]

setuptools.setup(
    # The distribution is `schwaby`; the importable package is still `schwab`.
    # Those differ deliberately -- see the note in README.rst. It means a
    # drop-in replacement for the original at the cost of never being
    # installable alongside it.
    name='schwaby',
    version=version,
    # Authorship stays with the original author of the code this began from.
    # His contact details are deliberately not carried over: support for this
    # project should not land in his inbox.
    #
    # No maintainer_email either, and that is deliberate rather than an
    # omission. An address in package metadata is permanent, scraped, and a
    # worse place to report a bug than the tracker -- where the report is
    # searchable, other people can see it has already been raised, and it
    # cannot be lost in a mailbox. The Tracker project URL below is the
    # supported route and the README says so.
    author='Alex Golec',
    maintainer='Tom Hirt',
    description=('Unofficial Python client for the Charles Schwab API, built '
                 'for systematic trading against live accounts'),
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url='https://github.com/Hu1kSmash/schwaby',
    # include= rather than a bare find_packages(), which also matched `tests`
    # and shipped a top-level `tests` module into every user's site-packages.
    # Anything else installing a top-level `tests` then collides with it
    # file-for-file, and `import tests` from outside a project root resolves
    # here. Published that way through 2.6.0.
    packages=setuptools.find_packages(include=['schwab', 'schwab.*']),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Development Status :: 5 - Production/Stable',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Topic :: Office/Business :: Financial :: Investment',
    ],
    python_requires='>=3.10',
    install_requires=[
        'authlib>=1.8',
        'httpx2>=2.12.0',
        'websockets>=14.0',

        # The interactive login flow runs a callback server in a separate
        # process. These were an optional `login` extra in 2.3.0 and are hard
        # dependencies again as of 3.0.0: the split saved twelve packages for
        # nobody who existed, and cost three silent failure modes -- pip freeze
        # drops extras, a consumer's deploy check could not evaluate an
        # extras-bearing requirement line, and the machinery needed its own
        # error path and tests.
        'flask',
        'multiprocess',
        'psutil',
    ],
    extras_require={
        # Kept, and deliberately empty. Anyone pinned to `schwaby[login]` or
        # `schwaby[codegen]` keeps working with no pip warning; the extras are
        # now no-ops because everything they named is installed anyway.
        'login': [],
        'codegen': [],
        # A literal list since 3.0.0. It used to be composed from the other
        # extras, because the suite starts flask servers through multiprocess
        # and a package listed in an extra but not in dev produced a green
        # local run against a stale virtualenv and a red CI. Those packages are
        # in install_requires now, so dev gets them either way.
        #
        # autopep8 is here rather than in `codegen`, which is where it used to
        # live: `make fix` runs it, and that is a maintainer's tool, not a
        # feature of the library.
        'dev': [
            'autopep8',
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
        'Documentation': 'https://github.com/Hu1kSmash/schwaby/blob/main/docs/index.rst',
        'Source': 'https://github.com/Hu1kSmash/schwaby',
        'Tracker': 'https://github.com/Hu1kSmash/schwaby/issues',
        'Upstream': 'https://github.com/alexgolec/schwab-py',
    },
    license='MIT',
    scripts=[
        'bin/schwab-generate-token.py',
    ],
)

