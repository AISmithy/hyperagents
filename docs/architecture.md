# Hyperagents POC Architecture

## Goal

Translate the core research idea from the HyperAgents paper into a minimal, understandable framework.

## Concept Mapping

Paper concept:

- task agent
- meta agent
- self-referential editable program
- archive of stepping stones
- evaluation-driven open-ended improvement

POC implementation:

- `task_policy`: weighted review policy for a simulated paper-review task
- `meta_policy`: mutation policy that changes task weights, threshold, review style, and its own mutation settings
- `hyperagent`: one object containing both policies plus lineage notes
- `archive`: all discovered agent variants with scores and parent links
- `engine`: parent selection, mutation, evaluation, archive updates, and progress tracking

## Why A Deterministic Domain

The paper uses FM-backed agents with tool use. That is too large for a first implementation. The paper-review simulator preserves the structure of improvement while keeping the system:

- cheap to run
- interpretable
- debuggable
- easy to compare across iterations

## Backend Flow

1. Create an initial hyperagent.
2. Evaluate it on train and test examples.
3. Add it to the archive.
4. Repeatedly:
   - choose a parent from the archive
   - use the parent meta policy to mutate task and meta policies
   - evaluate the child
   - store the child in the archive
   - update best-known progress

## Self-Modification In This POC

The task policy can change:

- feature weights
- accept/reject threshold
- reviewer persona

The meta policy can change:

- focus metric
- mutation step size
- threshold step size
- exploration strength
- memory notes about what failed

This is the key property the paper highlights: the mechanism that creates future variants is itself part of the editable agent.

## Frontend Role

The React app is a run inspector, not just a demo shell. It answers:

- Which agent is currently best?
- Which parent produced which child?
- Did improvement come from the task policy, the meta policy, or both?
- Is progress monotonic or exploratory?

## Natural Next Iterations

1. Persist the archive to disk.
2. Add baseline modes:
   - fixed meta agent
   - no archive
3. Replace heuristic mutation with LLM-produced edits.
4. Replace the simulator with a real benchmark domain.
