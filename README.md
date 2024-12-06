<div align="center">

<img src="docs/assets/swe-rex-logo.png" alt="SWE-ReX" style="height: 12em"/>

# SWE-agent Remote Execution Framework

[![Pytest](https://github.com/SWE-agent/swe-rex/actions/workflows/pytest.yaml/badge.svg)](https://github.com/SWE-agent/swe-rex/actions/workflows/pytest.yaml)
[![Check Markdown links](https://github.com/SWE-agent/swe-rex/actions/workflows/check-links.yaml/badge.svg)](https://github.com/SWE-agent/swe-rex/actions/workflows/check-links.yaml)
[![build-docs](https://github.com/SWE-agent/swe-rex/actions/workflows/build-docs.yaml/badge.svg)](https://github.com/SWE-agent/swe-rex/actions/workflows/build-docs.yaml)
</div>

SWE-ReX is a runtime interface for interacting with sandboxed shell environments, allowing you to effortlessly let your AI agent run *any command* on *any environment*.

Whether commands are executed locally or remotely in Docker containers, AWS remote machines, Modal, or something else, your agent code remains the same.
Running 100 agents in parallel? No problem either!

Specifically, SWE-ReX allows your agent to

* ✅ Interact with a **running shell session**. SWE-ReX will recognize when commands are finished, extract the output and exit code and return them to your agent.
* ✅ Let your agent use **interactive commands** like `ipython`, `gdb` or more in the shell.
* ✅ Interact with **multiple such shell sessions in parallel**, similar to how humans can have a shell, ipython, gdb, etc. all running at the same time.

## Why SWE-ReX?

We built SWE-ReX to help you focus on developing and evaluating your agent, not on infrastructure.

SWE-ReX came out of our experiences with [SWE-agent][].
With SWE-ReX, we

* ✅ Support **fast, massively parallel** agent runs (which made evaluating on large benchmarks a breeze).
* ✅ Support running commands on machines without Docker or to support non-Linux machines.
* ✅ Disentangle agent logic from infrastructure concerns, making SWE-agent more stable and easier to maintain.

## Install

```bash
pip install swe-rex
# With modal support
pip install 'swe-rex[modal]'
# With fargate support
pip install 'swe-rex[fargate]'
# Development setup (all optional dependencies)
pip install 'swe-rex[dev]'
```

Then head over to [our documentation](https://swe-rex.com/) to learn more!


[SWE-agent]: https://swe-agent.com
