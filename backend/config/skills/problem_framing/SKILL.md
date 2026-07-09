---
name: problem_framing
description: >-
  Decompose the user request into intent, required facts, and answer shape before
  committing to tool calls. Use when the user asks an open or multi-part question,
  when intent is ambiguous, or when the answer depends on world state that must be
  gathered first.
display_name: Problem framing
category: reasoning
side_effect_level: none
activation_mode: phase_mapped
allowed_in_react_states: [plan]
allowed_tool_groups: [read]
implementation:
  mode: prompt
runtime: {}
---

# Problem framing

You are in the **Plan** phase. Before naming any tool, produce a short structured frame:

1. **Intent** — one sentence: what the user actually wants to know or do.
2. **Facts needed** — the concrete claims that must be grounded in live graph state or command output (not assumed).
3. **Answer shape** — the form the final reply should take (a location, a list, a yes/no with reason, etc.).

Rules:
- Do not answer the question in Plan. Do not invent nodes, rooms, entities, or command results.
- If intent is ambiguous, state the single most likely interpretation you will proceed with; do not stall.
- Prefer the smallest set of read-only tools (look / find / describe / space) that can verify the facts needed. Note which tool verifies which fact.
- Match the user's language in the final answer; keep the frame itself concise.
