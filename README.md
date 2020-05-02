Basket management
=================

Pitch: a stallholder at the market receive orders in advance from his customers,
he will then prepare the basket so that customer save some time.

The system is also useful for handling reservation and pre-order.


Development environment
-----------------------

Development should be possible on any platform although the only tested
platform is Ubuntu.

This is a Python/Django project. It is backed on a simple Sqlite3 database.
PostgreSQL may replace Sqlite3 in further developments.

System requirements:

* Python 3
* pip
* virtualenv + virtualenvwrapper is highly recommended
* gettext must be available system-wide (see Django i18n framework)


Install
-------

    # Get application code
    git clone <project repository>
    cd <project dir>/

    # Install 3rd-party python modules
    python3 -m pip install -r requirements.txt
    python3 -m pip install -r requirements-dev.txt

    # Install 3rd-party front-end modules
    npm install

    # Set instance-specific settings
    cp <project>/local_settings.py.example <project>/local_settings.py
    # edit <project>/local_settings.py

    # Create database schema
    python3 manage.py migrate

    # Run test suite
    python3 manage.py test <app>

    # Run development server
    python3 manage.py runserver


Translations
------------

Please update catalog with option `--add-location file`:

    python3 manage.py makemessages -l fr --add-location file

That way, line numbers are omitted and the `django.po` will not change as
frequently. This makes Git history much more readable and avoid the hassle
of pointless conflict resolution when rebasing.

Semantic versioning
-------------------

Version numbering is automated with `npm`. Just run this:

    npm version major|minor|patch -m "Tag new version"

Choose between `major`, `minor` and `patch` depending on the level of version
increment you're after.

Note that your repository must be clean for this to work. Please do commit,
stash or ignore modified and untracked files.

This command will:
* update version number in `package.json`
* update version number in `locale/[...]/django.po`
* run `git commit` using message "Tag new version"
* run `git tag` to mark this version in git history

This command acts locally. Remember to ̀`push` with `--tags` when you want to
share this version:

    git push origin --tags
