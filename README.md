# Playground repository for remote execution layer

## The files

* `runtime.py`: This will actually execute the commands etc.
* `remote.py`: The server that serves results from the runtime
* `local.py`: The client that sends requests to the server

## Install

```
pip install -e .
```

## Running it

First, start server:

```
swebridge-remote
```

Then, in another terminal, run the client:

```
./examples/examples.py
```
