

from local import AbstractRuntime
from models import Observation, Action, CloseRequest, CreateShellRequest


class Session:
    def __init__(self):
        print("Session created")
    
    def run(self, command: str) -> Observation:
        print(f"Running command: {command!r}")
        return Observation(output="output", exit_code=0)
    
    def close(self):
        print("Session closed")


class Runtime(AbstractRuntime):
    def __init__(self):
        self.sessions: dict[str, Session] = {}
    
    def create_shell(self, request: CreateShellRequest):
        assert request.name not in self.sessions
        shell = Session()
        self.sessions[request.name] = shell
    
    def run(self, action: Action) -> Observation:
        return self.sessions[action.session].run(action.command)
    
    def close(self, request: CloseRequest):
        self.sessions[request.session].close()
        del self.sessions[request.session]
