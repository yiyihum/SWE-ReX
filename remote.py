#!/usr/bin/env python3


from fastapi import FastAPI

from models import Action, CloseRequest, CreateShellRequest
from runtime import Runtime

app = FastAPI()
runtime = Runtime()


@app.get("/")
async def root():
    return {"message": "running"}


@app.post("/create_shell")
async def create_shell(request: CreateShellRequest):
    runtime.create_shell(request)
    return {"message": "shell created"}

@app.post("/run")
async def run(action: Action):
    obs = runtime.run(action)
    return obs.model_dump()


@app.post("/close")
async def close(request: CloseRequest):
    runtime.close(request)
    return {"message": "shell closed"}
