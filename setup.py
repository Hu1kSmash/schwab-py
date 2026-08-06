import setuptools

with open('README.rst', 'r') as f:
    long_description = f.read()

with open('schwab/version.py', 'r') as f:
    '''Version looks like `version = '1.2.3'`'''
    version = [s.strip() for s in f.read().strip().split('=')][1]
    version = version[1:-1]

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
        'autopep8',
        'authlib>=1.6.0',
        'certifi>=2025.6.15',
        'flask',
        'httpx>=0.28.1',
        'multiprocess',
        'psutil',
        'python-dateutil',
        'urllib3',
        'websockets>=14.0'
    ],
    extras_require={
        'dev': [
            'callee',
            'colorama',
            'coverage',
            'nose',
            'pytest',
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

