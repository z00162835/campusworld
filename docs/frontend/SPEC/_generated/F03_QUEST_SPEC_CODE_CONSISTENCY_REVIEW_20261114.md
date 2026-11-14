# Quest SPEC / Code Consistency Review

**Status:** reviewed; identified implementation defects fixed; full activation not approved
**Generated:** 2026-11-14
**Scope:** current tracked and untracked G2–G4 implementation, not only committed HEAD
**Active plan:** [implementation plan](F03_QUEST_WORLD_INTERACTION_IMPLEMENTATION_PLAN.md)
**Contracts:** [interaction](../features/F03_AI_NATIVE_QUEST_INTERACTION.md), [runtime](../../../task/SPEC/features/F06_AI_NATIVE_QUEST_RUNTIME_REFACTOR.md)

## Conclusion

Architecture direction and implemented slices match the approved contracts. Implementation and acceptance are not interchangeable: the feature remains non-Active, and real automatic operation is not yet delivered. No production rules were invented, installed or enabled. PostgreSQL integration and authenticated UI acceptance remain deferred by the approved scope.

## Corrected inconsistencies

| Priority | Contract / observed behavior | Correction and evidence |
| --- | --- | --- |
| High | Account cursor must precede object locks. Choice preview previously acquired shared graph locks before the executor requested exclusive locks; concurrent requests could form a lock-upgrade deadlock. | `quest_governance.py` has nonlocking preview mode; `world_interaction/service.py` uses it for preparation and lets the executor instantiate fresh locking governance after scope locks. Unit coverage checks preview SQL has no row locks and execution evaluation retains locks. Actual PG concurrency acceptance is still required. |
| Medium | Foreground Quest owns dialogue even without an active Objective. Help/toolbar previously depended on activeTask, and ordinary input could reuse a different Quest/Agent thread. | `worldSession.ts` derives foreground context, scopes/restores threads by Quest + Agent + collaboration ID, refreshes Objective/revision, and separates generic input after untracking. QuestTracker retains Companion access without an active task; toolbar and flow use foreground identity. Store/component tests cover these cases. |
| Medium | Process templates permit only current Quest/Objective ID substitution. Python format previously admitted attribute/index/format extensions and could raise uncaught exceptions during preview. | `render_quest_template` is shared by compilation, evaluation and execution; only the two plain fields are accepted. Invalid syntax, attributes, subscripts, conversion and format specifications are covered by rejection tests. |
| Medium | Objective visibility must use the existing Task ACL/visibility contract, not semantic-node ownership. Conversation validation could reject pool-visible tasks that projection already exposed. | Context validation now calls shared `visible_task_ids`; positive/negative tests cover a visible task without semantic ownership and an unavailable task. |

## Contract matrix

| Area | Code evidence | State |
| --- | --- | --- |
| G1 graph selections, revision, visibility | interaction services/projection and command dispatch | implemented; PG acceptance pending |
| G2 structured dialogue and identity | session store, Companion/toolbar, existing authorized SSE/Memory thread binding | implemented slice; full map-focus/pinned-rule/Evidence reference pack and completion/closure lifecycle hook pending |
| G2 truthful choices and independent authorization | graph governance, pure composition, registry authorization, scoped mutation permit | implemented bounded schema; production publication/version immutability not yet enforced by an authoring workflow |
| G3 explicit execution and audit | executor, task runs/events, AgentRunRecord, projection cursor | implemented transactional-command service; sensing/Agent scheduler entry pending |
| G3 memory and escalation | collaboration archive/redaction; visible task event Feedback/Pulse | implemented slices; full Quest lifecycle handoff and PG proof pending |
| G4 game-native interaction | six components, Map-canvas compact layers, Journal linkage, keyboard separators | component-tested; authenticated mobile/accessibility/experience acceptance pending |

## Next implementation order

1. Implement canonical Quest lifecycle entry points together with archive hooks, role/version/audit enforcement and verification/override evidence. Never infer Quest acceptance from `task done` or archive by mutating GET projections.
2. Connect the shared explicit executor to an actual Agent scheduler/driver with the real Agent Principal, published finite capabilities, scoped idempotency and cancellation. Do not introduce arbitrary model-generated commands or default production SOPs.
3. Integrate governed source publication: enforce semantic version uniqueness and published-definition immutability at its write boundary; exact-read lookup alone is not publication governance. Keep production activation disabled until this boundary is verified.
4. Execute deferred PG persistence/concurrency and authenticated UI/accessibility gates only when the user authorizes them. Formal asynchronous learning publication remains a later runtime gate, not a substitute for safe raw memory handoff.

Live verification results belong to [ACCEPTANCE](../ACCEPTANCE.md); executable backlog belongs to [TODO](../TODO.md). This review is an execution snapshot, not another active plan or a new behavior source of truth.
