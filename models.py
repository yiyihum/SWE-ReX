from pydantic import BaseModel

class Observation(BaseModel):
    output: str
    error: str = ""
    exit_code: int = 0


class CreateShellRequest(BaseModel):
    name: str


class CreateShellResponse(BaseModel):
    ...


class Action(BaseModel):
    command: str
    session: str


class CloseRequest(BaseModel):
    session: str
