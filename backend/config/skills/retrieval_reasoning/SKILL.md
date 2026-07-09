---
name: retrieval_reasoning
description: >-
  Plan and execute read-only retrieval over the live graph (look / find / describe /
  space) to ground factual claims. Use when the user asks about world state,
  locations, entities, or needs verified context before an answer can be trusted.
display_name: Retrieval reasoning
category: retrieval
side_effect_level: none
activation_mode: phase_mapped
allowed_in_react_states: [plan, do]
allowed_tool_groups: [read]
implementation:
  mode: prompt
runtime: {}
---

# Retrieval reasoning

You may invoke read-only discovery tools. Treat every factual claim about the live
world as unverified until a tool observation confirms it.

Workflow:
1. Decide which read-only tool answers each fact listed in the Plan frame.
2. Call tools one batch at a time; never claim a tool ran unless its observation is in the conversation.
3. After observations arrive, reconcile them against the facts needed: mark each fact *verified*, *contradicted*, or *missing*.
4. If a fact is missing, gather it with another read-only call before drafting the answer.

Rules:
- Only use tools in the read group (look / find / describe / space / help / whoami / primer / agent). Do not call state-changing commands.
- Do not fabricate node ids, room names, or entity attributes. If retrieval returns nothing, say so.
- Keep tool arguments minimal and specific; avoid broad scans when a targeted lookup suffices.
- Observations are the single source of truth for live state; memory and prior turns are hints, not evidence.
