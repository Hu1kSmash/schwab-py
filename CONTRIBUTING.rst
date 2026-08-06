=============================
Contributing to ``schwab-py``
=============================

Fixing a bug? Adding a feature? Just cleaning up for the sake of cleaning up?
Great! No improvement is too small, and pull requests are welcome. Read this
guide to learn how to set up your environment so you can contribute.

.. note::

   **This is a fork of** `alexgolec/schwab-py
   <https://github.com/alexgolec/schwab-py>`__.

   If your change is not specific to this fork's changes — see `CHANGELOG.md
   <https://github.com/Hu1kSmash/schwab-py/blob/main/CHANGELOG.md>`__ — please
   consider sending it upstream as well, or instead. It will help more people
   there, and every change which lands upstream is one less this fork has to
   carry. Contributions are welcome here either way.

   `MAINTAINING.md
   <https://github.com/Hu1kSmash/schwab-py/blob/main/MAINTAINING.md>`__
   describes the branch layout, which matters if you intend to send the same
   change to both.

------------------------
A Note About the Testing
------------------------

The test suite mocks the network. It proves this library builds the request it
intended to build; it says nothing about whether the API accepts it or whether
the result is correct.

That distinction has mattered. Every defect found in this library so far has
been in code with 100% line coverage — prices silently a cent low, a token file
a crash could destroy, an enum advertising values the venue rejects, redaction
which never ran. Coverage measures which lines executed, not whether what they
produced was right.

So when you add a test, **revert your fix and watch it fail.** A test which
passes either way is worse than no test, because it looks like protection.

And if a behaviour can only be established against the live API, say so in the
pull request, say what you observed, and say when. That is a perfectly good
answer and a more honest one than a mocked test implying more than it proves.

------------------------------
Setting up the Dev Environment
------------------------------

Dependencies are listed in the `requirements.txt` file. These development 
requirements are distinct from the requirements listed in `setup.py` and include 
some additional packages around testing, documentation generation, etc.

Before you install anything, I highly recommend setting up a `virtualenv` so you 
don't pollute your system installation directories:

.. code-block:: shell

  pip install virtualenv
  virtualenv -v virtualenv
  source virtualenv/bin/activate

Next, install project requirements:

.. code-block:: shell

  pip install ".[dev]"

Finally, verify everything works by running tests:

.. code-block:: shell

  make test

At this point you can make your changes.

Note that if you are using a virtual environment and switch to a new terminal
your virtual environment will not be active in the new terminal,
and you need to run the activate command again.
If you want to disable the loaded virtual environment in the same terminal window,
use the command:

.. code-block:: shell

  deactivate

----------------------
Development Guidelines
----------------------

+++++++++++++++++
Test your changes
+++++++++++++++++

This project aims for high test coverage. All changes must be properly tested, 
and we will accept no PRs that lack appropriate unit testing. We also expect 
existing tests to pass. You can run your tests using: 

.. code-block:: shell

  make test

++++++++++++++++++
Document your code
++++++++++++++++++

Documentation is how users learn to use your code, and no feature is complete 
without a full description of how to use it. If your PR changes external-facing 
interfaces, or if it alters semantics, the changes must be thoroughly described 
in the docstrings of the affected components. If your change adds a substantial 
new module, a new section in the documentation may be justified. 

Documentation is built using `Sphinx <https://www.sphinx-doc.org/en/master/>`__:

.. code-block:: shell

  sphinx-build docs/ docs-build
