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
    return (await runtime.create_shell(request)).model_dump()


@app.post("/run")
async def run(action: Action):
    return (await runtime.run(action)).model_dump()


@app.post("/close")
async def close(request: CloseRequest):
    return (await runtime.close(request)).model_dump()
