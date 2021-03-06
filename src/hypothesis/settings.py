"""A module controlling settings for Hypothesis to use in falsification.

Either an explicit Settings object can be used or the default object on
this module can be modified.

"""
import os

USE_DEFAULT = object()


def set_or_default(self, name, value):
    if value != USE_DEFAULT:
        setattr(self, name, value)
    else:
        setattr(self, name, getattr(default, name))


class Settings(object):

    """A settings object controls a variety of parameters that are used in
    falsification. There is a single default settings object that all other
    Settings will use as its values s defaults.

    Not all settings parameters are guaranteed to be stable. However the
    following are:

    max_examples: Once this many examples have been considered without finding
        any counter-example, falsify will terminate
    timeout: Once this amount of time has passed, falsify will terminate even
        if it has not found many examples. This is a soft rather than a hard
        limit - Hypothesis won't e.g. interrupt execution of the called
        function to stop it.
    derandomize: If this is True then hypothesis will run in deterministic mode
        where each falsification uses a random number generator that is seeded
        based on the hypothesis to falsify, which will be consistent across
        multiple runs. This has the advantage that it will eliminate any
        randomness from your tests, which may be preferable for some situations
        . It does have the disadvantage of making your tests less likely to
        find novel breakages.
    database: An instance of hypothesis.database.ExampleDatabase that will be
        used to save examples to and load previous examples from. May be None
        in which case no storage will be used.

    """
    # pylint: disable=too-many-arguments

    def __init__(
            self,
            min_satisfying_examples=USE_DEFAULT,
            max_examples=USE_DEFAULT,
            max_skipped_examples=USE_DEFAULT,
            timeout=USE_DEFAULT,
            derandomize=USE_DEFAULT,
            database=USE_DEFAULT,
    ):
        set_or_default(
            self, 'min_satisfying_examples', min_satisfying_examples)
        set_or_default(
            self, 'max_examples', max_examples)
        set_or_default(
            self, 'max_skipped_examples', max_skipped_examples)
        set_or_default(
            self, 'timeout', timeout)
        set_or_default(
            self, 'derandomize', derandomize)
        set_or_default(
            self, 'database', database)


default = Settings(
    min_satisfying_examples=5,
    max_examples=200,
    timeout=60,
    max_skipped_examples=50,
    derandomize=False,
    database=None
)

DATABASE_OVERRIDE = os.getenv('HYPOTHESIS_DATABASE_FILE')

if DATABASE_OVERRIDE:
    from hypothesis.database import ExampleDatabase
    from hypothesis.database.backend import SQLiteBackend
    default.database = ExampleDatabase(
        backend=SQLiteBackend(DATABASE_OVERRIDE)
    )
