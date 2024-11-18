from typing import Any


class SweRexception(Exception):
    """Any exception that is raised by SWE-Rex."""


class SessionNotInitializedError(SweRexception, RuntimeError):
    """Raised if we try to run a command in a shell that is not initialized."""


class NonZeroExitCodeError(SweRexception, RuntimeError):
    """Can be raised if we execute a command in the shell and it has a non-zero exit code."""


class BashIncorrectSyntaxError(SweRexception, RuntimeError):
    """Before running a bash command, we check for syntax errors.
    This is the error message for those syntax errors.
    """

    def __init__(self, message: str, *, extra_info: dict[str, Any] = None):
        super().__init__(message)
        if extra_info is None:
            extra_info = {}
        self.extra_info = extra_info


class CommandTimeoutError(SweRexception, RuntimeError, TimeoutError): ...


class NoExitCodeError(SweRexception, RuntimeError): ...


class SessionExistsError(SweRexception, ValueError): ...


class SessionDoesNotExistError(SweRexception, ValueError): ...


class DeploymentNotStartedError(SweRexception, RuntimeError):
    def __init__(self, message="Deployment not started"):
        super().__init__(message)
