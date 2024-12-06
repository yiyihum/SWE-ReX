# SWE-ReX

<div style="text-align:center">
    <img src="assets/swe-rex-logo.png" alt="SWE-ReX" style="height: 12em"/>
</div>

SWE-ReX is a runtime interface for interacting with sandboxed shell environments, allowing you to effortlessly let your AI agent run *any command* on *any environment*.

Whether commands are executed locally or remotely in [Docker](https://www.docker.com/) containers, [AWS remote machines](https://aws.amazon.com/fargate/), [Modal](https://modal.com/), or something else, your agent code remains the same.
Running 100 agents in parallel? No problem either!

## Why SWE-ReX?

We built SWE-ReX to help you focus on developing and evaluating your agent, not on infrastructure.

SWE-ReX came out of our experiences with [SWE-agent][], which executed agent commands in a bash session running in a Docker container. 
However, this

* Introduced a lot of complexity to the codebase, because interacting with running bash sessions is hard, especially when adding interactive commands to the agent.
* Made it hard to run commands on machines without Docker or to support non-Linux machines.
* Made it hard to run multiple agents in parallel (which made evaluating on large benchmarks a pain).

By separate out our most annoying infrastructure parts to SWE-ReX, we made SWE-agent faster, more stable, and easier to maintain.

[SWE-agent]: https://swe-agent.com