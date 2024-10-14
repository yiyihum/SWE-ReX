import time

import pexpect

from local import AbstractRuntime
from models import Action, CloseRequest, CloseResponse, CreateShellRequest, CreateShellResponse, Observation


class Session:
    def __init__(self):
        self._ps1 = "SHELLPS1PREFIX"
        self.shell = None

    def start(self) -> CreateShellResponse:
        self.shell = pexpect.spawn(
            "/bin/bash",
            encoding="utf-8",
            echo=False,
        )
        time.sleep(0.1)
        self.shell.sendline("echo 'fully_initialized'")
        try:
            self.shell.expect("fully_initialized", timeout=1)
        except pexpect.TIMEOUT:
            return CreateShellResponse(success=False, failure_reason="timeout while initializing shell")
        output = self.shell.before
        self.shell.sendline(f"umask 002; export PS1='{self._ps1}'; export PS2=''")
        try:
            self.shell.expect(self._ps1, timeout=1)
        except pexpect.TIMEOUT:
            return CreateShellResponse(success=False, failure_reason="timeout while setting PS1")
        output += "\n---\n" + self.shell.before  # type: ignore
        return CreateShellResponse(output=output)

    def run(self, action: Action) -> Observation:
        if self.shell is None:
            return Observation(output="", exit_code_raw="-300", failure_reason="shell not initialized")
        self.shell.sendline(action.command)
        try:
            self.shell.expect(self._ps1, timeout=action.timeout)
        except pexpect.TIMEOUT:
            return Observation(output="", exit_code_raw="-100", failure_reason="timeout while running command")
        output: str = self.shell.before  # type: ignore
        self.shell.sendline("echo $?")
        try:
            self.shell.expect(self._ps1)
        except pexpect.TIMEOUT:
            return Observation(output="", exit_code_raw="-200", failure_reason="timeout while getting exit code")
        exit_code_raw: str = self.shell.before  # type: ignore
        return Observation(output=output, exit_code_raw=exit_code_raw)

    def close(self) -> CloseResponse:
        if self.shell is None:
            return CloseResponse()
        self.shell.close()
        self.shell = None
        return CloseResponse()


class Runtime(AbstractRuntime):
    def __init__(self):
        self.sessions: dict[str, Session] = {}

    def create_shell(self, request: CreateShellRequest) -> CreateShellResponse:
        assert request.name not in self.sessions
        shell = Session()
        self.sessions[request.name] = shell
        return shell.start()

    def run(self, action: Action) -> Observation:
        return self.sessions[action.session].run(action)

    def close(self, request: CloseRequest) -> CloseResponse:
        out = self.sessions[request.session].close()
        del self.sessions[request.session]
        return out
