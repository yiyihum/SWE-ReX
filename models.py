from pydantic import BaseModel

class Observation(BaseModel):
    output: str
    exit_code_raw: str = ""
    failure_reason: str = ""

    @property
    def exit_code(self) -> int:
        try:
            return int(self.exit_code_raw)
        except ValueError:
            return -1
    
    @property
    def success(self) -> bool:
        return self.exit_code == 0


class CreateShellRequest(BaseModel):
    name: str = "default"


class CreateShellResponse(BaseModel):
    success: bool = True
    failure_reason: str = ""
    output: str = ""


class Action(BaseModel):
    command: str
    session: str = "default"
    timeout: float|None = None


class CloseRequest(BaseModel):
    session: str = "default"


class CloseResponse(BaseModel):
    ...