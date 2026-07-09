---
name: final_synthesis
description: >-
  Synthesize a grounded final answer from verified observations and the draft.
  Use in the Check and Act phases to confirm completeness, drop unverified
  claims, and present the reply in the user's language.
display_name: Final synthesis
category: finalization
side_effect_level: none
activation_mode: phase_mapped
allowed_in_react_states: [check, act]
allowed_tool_groups: [read]
implementation:
  mode: prompt
runtime: {}
---

# Final synthesis

You are finishing the answer. Apply these gates before producing user-visible text:

1. **Completeness** — every fact the user asked for is backed by a tool observation. If a fact is missing, either retrieve it (if budget remains) or explicitly state it is unknown.
2. **No fabrication** — remove any room name, entity, id, or command result that does not appear in an observation. Invention is never acceptable.
3. **Grounding** — keep claims tied to observations; do not generalize beyond what was retrieved.
4. **Concision & language** — answer in the user's language, as directly as the question allows. Drop internal phase tags, planning notes, and tool-JSON.

In the **Check** phase, flag the draft as incomplete (emit `RETRY: need_tools=...` naming the missing read-only tools) only when a required fact is genuinely missing and the tool budget allows another round. Otherwise mark the draft acceptable.

In the **Act** phase, output only the final user-facing reply.
