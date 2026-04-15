"""
core/base.py
Strict internal module contract for MicroLabxAI.

`setup/get/set` are the internal runtime hooks.
The future user-facing API should wrap these into simpler verbs such as
`add/read/update` at the workspace level.
"""


class BaseModule:
    """
    Base contract followed by every runtime module.

    Required metadata:
    - TYPE
    - PROTOCOL
    - DESCRIPTION

    Optional declarative metadata:
    - SETUP_FIELDS
    - READ_FIELDS
    - SET_FIELDS
    """

    TYPE = ""
    PROTOCOL = ""
    DESCRIPTION = ""

    # Used by interactive setup and AI-assisted configuration.
    SETUP_FIELDS = []
    READ_FIELDS = []
    SET_FIELDS = []

    @classmethod
    def setup(cls, config):
        """Create and return the low-level driver instance."""
        raise NotImplementedError("%s.setup() is not implemented." % cls.__name__)

    @classmethod
    def get(cls, driver, options=None):
        """Read data from the hardware and return a dictionary payload."""
        raise NotImplementedError("%s.get() is not implemented." % cls.__name__)

    @classmethod
    def set(cls, driver, updates):
        """Update the hardware or module configuration and return a result dictionary."""
        raise NotImplementedError("%s.set() is not implemented." % cls.__name__)
