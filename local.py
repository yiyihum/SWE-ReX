#!/usr/bin/env python3

from abc import ABC, abstractmethod

import requests

from models import Action, CloseRequest, CloseResponse, CreateShellRequest, CreateShellResponse, Observation


class AbstractRuntime(ABC):
    @abstractmethod
    def create_shell(self, request: CreateShellRequest) -> CreateShellResponse:
        pass

    @abstractmethod
    def run_in_shell(self, action: Action) -> Observation:
        pass

    @abstractmethod
    def close_shell(self, request: CloseRequest):
        pass


class RemoteRuntime(AbstractRuntime):
    def __init__(self, host: str):
        self.host = host

    def is_alive(self) -> bool:
        try:
            response = requests.get(f"http://{self.host}")
            if response.status_code == 200 and response.json().get("message") == "running":
                return True
            return False
        except requests.RequestException:
            return False

    def create_shell(self, request: CreateShellRequest) -> CreateShellResponse:
        response = requests.post(f"http://{self.host}/create_shell", json=request.model_dump())
        response.raise_for_status()
        return CreateShellResponse(**response.json())

    def run_in_shell(self, action: Action) -> Observation:
        print("----")
        print(action)
        response = requests.post(f"http://{self.host}/run_in_shell", json=action.model_dump())
        response.raise_for_status()
        obs = Observation(**response.json())
        if not obs.success:
            print(f"Command failed: {obs.failure_reason}")
        return obs

    def close_shell(self, request: CloseRequest) -> CloseResponse:
        response = requests.post(f"http://{self.host}/close_shell", json=request.model_dump())
        response.raise_for_status()
        return CloseResponse(**response.json())


if __name__ == "__main__":
    runtime = RemoteRuntime("localhost:8000")
    # fmt: off
    print(runtime.is_alive())
    print(runtime.create_shell(CreateShellRequest()))
    print(runtime.run_in_shell(Action(command="python", is_interactive_command=True, expect=[">>> "])))
    print(runtime.run_in_shell(Action(command="print('hello world')", is_interactive_command=True, expect=[">>> "])))
    print(runtime.run_in_shell(Action(command="quit()\n", is_interactive_quit=True)))
    print( runtime.run_in_shell( Action( command="touch test && ls",)))
    print( runtime.run_in_shell( Action( command="echo 'test'",)))
    print( runtime.run_in_shell( Action( command="echo 'answer'",)))
    print(runtime.run_in_shell(Action(command="python", is_interactive_command=True, expect=[">>> "])))
    print(runtime.run_in_shell(Action(command="print('hello world')", is_interactive_command=True, expect=[">>> "])))
    print(runtime.run_in_shell(Action(command="quit()\n", is_interactive_quit=True)))
    print( runtime.run_in_shell( Action( command="touch test && ls",)))
    print( runtime.run_in_shell( Action( command="doesnexist",)))
    print(runtime.close_shell(CloseRequest()))
    # fmt: on
