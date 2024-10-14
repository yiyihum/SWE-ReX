#!/usr/bin/env python3

from abc import ABC, abstractmethod
import requests

from models import Action, CloseRequest, CreateShellRequest, CreateShellResponse, Observation


class AbstractRuntime(ABC):
    @abstractmethod
    def create_shell(self, request: CreateShellRequest) -> CreateShellResponse:
        pass

    @abstractmethod
    def run(self, action: Action) -> Observation:
        pass

    @abstractmethod
    def close(self, request: CloseRequest):
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

    def run(self, action: Action) -> Observation:
        response = requests.post(f"http://{self.host}/run", json=action.model_dump())
        response.raise_for_status()
        return Observation(**response.json())
    
    def close(self, request: CloseRequest):
        response = requests.post(f"http://{self.host}/close", json=request.model_dump())
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    runtime = RemoteRuntime("localhost:8000")
    print(runtime.is_alive())
    print(runtime.create_shell(CreateShellRequest()))
    print(runtime.run(Action(command="echo 'this is a test'")))
    print(runtime.run(Action(command="doesntexit")))
    print(runtime.close(CloseRequest()))