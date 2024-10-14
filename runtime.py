

import time
from local import AbstractRuntime
from models import CreateShellResponse, Observation, Action, CloseRequest, CreateShellRequest
import pexpect


class Session:
    def __init__(self):
        pass

    def start(self) -> CreateShellResponse:
        print("Session created")
        self._ps1= "SHELLPS1PREFIX"
        self.shell = pexpect.spawn(
            '/bin/bash',
            encoding='utf-8',
            echo=False,
        )
        time.sleep(0.1)
        self.shell.sendline("echo 'fully_initialized'")
        self.shell.expect("fully_initialized", timeout=1)
        output = self.shell.before
        self.shell.sendline(f"umask 002; export PS1='{self._ps1}'; export PS2=''")
        self.shell.expect(self._ps1)
        output += "\n---\n" + self.shell.before  # type: ignore
        return CreateShellResponse(output=output)
    
    def run(self, action: Action) -> Observation:
        print(f"Running command: {action.command!r}")
        self.shell.sendline(action.command)
        self.shell.expect(self._ps1, timeout=action.timeout)
        output: str = self.shell.before  # type: ignore
        self.shell.sendline('echo $?')
        self.shell.expect(self._ps1)
        exit_code_raw: str = self.shell.before  # type: ignore
        print('after', self.shell.after)
        return Observation(output=output, exit_code_raw=exit_code_raw)
    
    def close(self):
        print("Session closed")


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
    
    def close(self, request: CloseRequest):
        self.sessions[request.session].close()
        del self.sessions[request.session]
