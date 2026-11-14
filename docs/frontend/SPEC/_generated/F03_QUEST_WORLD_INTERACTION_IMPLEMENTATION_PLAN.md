# F03 Quest World Interaction Implementation Plan

**Status:** approved for implementation — G0 confirmed; G1 PostgreSQL acceptance pending; G2–G4 implementation slices delivered, lifecycle/worker and authenticated acceptance pending
**Generated:** 2026-10-11
**Execution snapshot updated:** 2026-11-14 (N01:A / N02:A / N03:B)
**Owner:** frontend + task runtime + world interaction + agent runtime
**Stable contract:** [`../features/F03_AI_NATIVE_QUEST_INTERACTION.md`](../features/F03_AI_NATIVE_QUEST_INTERACTION.md)
**Runtime dependency:** [`../../../task/SPEC/features/F06_AI_NATIVE_QUEST_RUNTIME_REFACTOR.md`](../../../task/SPEC/features/F06_AI_NATIVE_QUEST_RUNTIME_REFACTOR.md)

## 1. Objective

Current execution status is tracked in [`../TODO.md`](../TODO.md) and [`../ACCEPTANCE.md`](../ACCEPTANCE.md). The governed source evaluator, explicit transactional executor, scoped audit/escalation, six UI components and compact Map-canvas layers are implemented slices, not full gate acceptance. Remaining work includes Quest completion/closure archive hooks, real Agent scheduler integration, published customer rule packages, PostgreSQL transaction/concurrency verification and authenticated accessibility/experience acceptance. No integration tests or live rule publication are authorized by this snapshot.

Deliver the F03 experience as a world-native Quest loop rather than a traditional enterprise workbench:

```text
World Pulse
  -> Track Quest
  -> Inspect world entities and clues
  -> Converse with a Quest-bound Companion Agent
  -> Choose governed world actions
  -> Observe evidence and world feedback
  -> Continue, verify, re-plan, or learn
```

The implementation must preserve CampusWorld invariants:

- graph nodes and relationships remain the semantic-world source of truth;
- commands/services own business behavior across HTTP, SSH, CLI, Agent, and UI adapters;
- account `location_id` remains the authoritative current room;
- Objective transitions continue through `task_state_machine`;
- AI recommendations never replace deterministic authorization or policy gates;
- Agent automation is auditable even when no human action is required.

## 2. Approved decisions

This plan records the line-by-line human decisions received on 2026-10-11. Any change to these decisions requires updating the stable F03/F06 contract before implementation.

| Review item | Adopted decision | Delivery gate |
|---|---|---|
| P01 scope ownership | F03 owns interaction/read-model semantics; F06 owns Quest generation, policy, execution, and learning. This plan coordinates both but does not move runtime authority into frontend code. | G0 |
| P02 delivery sequence | R1 reuses current task/graph/runtime foundations and adds the approved projection, selection relations, collaboration, and Journal subgraph. Deeper Evidence/Outcome/Learning materialization remains later. | G0–G4 |
| P03 customer scene/fact graph | Persist explicit `TRACKS_QUEST`, `FOCUSES_ON`, and resolvable `PINS_CLUE` graph relations. Link account+Agent Memory to visible graph nodes/relations; Memory never replaces world facts. | G1, G2 |
| P04 Objective focus | `quest focus-objective` is a protocol-neutral, audited business-context command backed by `FOCUSES_ON`; it never implies claim/start/complete. | G1 |
| P05 policy and Agent learning | One object-sensitive Quest decision facade composes governance and Agent behavior decisions without replacing command authorization. Agent settings may evolve only from governed LearningProposal outputs applied as versioned configuration/Skill references. | G0, G2, G3 |
| P06 automatic execution | R2 uses an explicit orchestrator that invokes existing commands/services and records policy, actor, evidence, and result. Fully dynamic execution graphs are deferred. | G3 |
| P07 collaboration | Persist `ASSISTED_BY` as a multi-Agent Quest collaboration relation with role/lifecycle attributes; it grants no execution authority. | G1, G2 |
| P08 conversation lifecycle | Bind a thread immutably to Quest + actual Agent, retain the collaboration relationship reference, archive it on completion, and feed it into account+Agent episodic/LTM promotion without auto-publishing learned configuration. | G2, G3 |
| P09 concurrency | Use an opaque server projection revision plus last visible event ID and optimistic concurrency; do not rely on a frontend-only `stateVersion`. | G1, G2 |
| P10 consequence truth | Decision options distinguish `confirmed`, `predicted`, and `proposed` consequences with provenance/confidence where applicable. | G2 |
| P11 Pulse persistence | Derive Pulse facts from authoritative state/events; persist only per-user attention state such as seen/snoozed and governed disposition metadata. | G3 |
| P12 Journal graph | R1 includes a permission-filtered Quest relationship graph, not only a timeline. Unmaterialized semantic refs render as unresolved leaves. | G1, G4 |
| P13 progress | Derive progress from Objective states; no Agent/model-authored arbitrary percentage. | G1, G3 |
| P14 mobile experience | Keep Map as the world canvas and place the foreground Quest/Objective/action in a responsive HUD; use expandable Key Clues, Journal, and Companion layers. | G4 |
| P15 capability negotiation | Backend explicitly advertises contract version and capabilities; frontend does not infer support from incidental field presence. | G0, G1 |
| P16 acceptance | Require technical verification and measurable human/game-native UX outcomes. | G4 |

The implementation-level confirmations received on 2026-10-11 close the remaining contract choices:

| Review item | Adopted decision | Delivery gate |
|---|---|---|
| C01 release mapping | Phase 1 maps to runtime R1; governed planning and explicit automation map to R2; verification/learning map to R3/R4. | G0 |
| C02 policy composition | The Quest facade composes Quest governance, F16 behavior policy, and command authorization as separate audited planes; it does not merge their rule stores. | G0, G2, G3 |
| C03 clue materialization | R1 adds a minimal canonical `observation` graph node; Evidence verification enriches it in later releases without rewriting the original assertion. | G1 |
| C04 tracking cardinality | An account may actively track multiple Quests. One account-wide `FOCUSES_ON` selects the foreground Objective and therefore the HUD Quest. | G1 |
| C05 projection revision | A server-owned, account-scoped monotonic World Interaction revision plus last visible event ID governs optimistic concurrency. | G1, G2 |
| C06 transcript source | Memory Thread + STM/LTM is the transcript source of truth; `world_conversation_archive` is a compatibility read projection. | G2 |
| C07 thread schema | Reuse `agent_node_id`; add immutable `quest_node_id`, optional `collaboration_relationship_id`, creation revision, and archive metadata. | G2 |
| C08 attention persistence | Store high-churn per-account attention in `situation_attention`; keep Situation business state in graph/domain events. | G3 |
| C09 Journal boundary | The graph contains authoritative semantic nodes/edges; action/run/result records render as an auditable timeline overlay unless separately materialized by domain rules. | G1, G4 |
| C10 contract location | Stable F03 owns payload, capability, version compatibility, mutation-envelope, and stale-state behavior. | G0 |
| C11 learning activation | G1–G4 require safe archive-to-learning input only; full governed configuration promotion remains a later learning-loop deliverable. | G3, R4 |
| C12 UX thresholds | Use the approved quantitative orientation, completion, authorization-clarity, stale-recovery, keyboard, and screen-reader thresholds. | G4 |
| C13 Journal naming | `World Journal / 世界日志` is the top-level history surface; `Quest Journal / 任务日志` is the selected-Quest view. | G0, G4 |

## 3. Current architecture assessment

### 3.1 Backend

| Area | Current implementation | Gap |
|---|---|---|
| Quest semantic shell | `quest_semantic_service.py` creates/shows Situation, Goal, Quest and derives Objective aggregates. | World interaction does not consume the authoritative Quest projection. |
| User work selection | `user_task_queue.py` returns visible tasks; world interaction selects `queue[0]`. | No explicit tracked Quest or multi-Objective journal selection. |
| World interaction | `WorldInteractionService` aggregates map, context, queue events, and active task. | Adapter is task-first and contains Quest projection SQL/ORM logic that belongs in a task read service. |
| Actions | `decision_event_id + option_id` resolves to commands; task actions use the shared task state machine. | Options lack consequence/gate/evidence metadata and return hard-coded English labels. |
| Conversation | `/decision-center/query/stream` invokes `aico <text>` through `CommandRunner`; AICO builds world snapshot and STM/LTM context. | Request has no structured Quest context or Companion identity. |
| Memory | Conversation STM, per-user+Agent LTM scope, `graph_node_id / relationship_id`, and thread directory already exist. | Thread directory has no immutable Quest/actual-Agent binding or collaboration reference; async promotion and governed learning handoff remain incomplete. |
| Automation audit | `task_state_transitions`, `task_runs`, `task_events`, `agent_run_records`, and outbox already provide audit substrates. | No Quest World Feedback projection and not every automatic path is proven to write the required records. |
| Policy | Existing command authorization protects command execution. | Quest governance and F16 behavior decisions are not yet correlated behind the Quest facade while preserving separate records and final authorization. |
| Semantic map | `semantic-map` select/drill returns `focus_map` plus inspect data; it does not modify `location_id`. | Situation supports one `subject_ref`; multi-entity impact projection is absent. |

### 3.2 Frontend

| Area | Current implementation | Gap |
|---|---|---|
| Session SSOT | `worldSession` owns the aggregate interaction payload. | Payload has no explicit Quest Journal, World Feedback, tracking status, or interaction-state version. |
| Quest projection | `decisionCenter` exposes one `activeTask`; `ActiveTaskCard` renders a compact Quest context. | `TaskCard` conflates Objective and Quest HUD; progress is synthetic. |
| Quest dialogue | Quest buttons submit localized text to the generic AICO stream. | Context is not structured; generic thread lifecycle is not Quest-scoped. |
| Map linkage | `subjectRef` selects a graph entity and `selectedInspect` drives map/context highlight. | No related entity set, impact scope, or route projection. |
| World Pulse | Decision events are queue task events with local hide behavior. | Situation lifecycle, snooze/dismiss semantics, and durable seen state are absent. |
| Accessibility | Keyboard basics and textual risk labels exist. | Focus transfer, live Quest updates, screen-reader semantics, and reduced-motion verification are incomplete. |

### 3.3 Existing assets to reuse

- Task visibility, ACL, assignment, transition ledger, runs, events, and outbox.
- `show_quest` Objective aggregation and semantic read authorization.
- `CommandRunner` and task/semantic commands as protocol-neutral behavior.
- AICO cancellation, streaming, STM/LTM, and world snapshot pipeline.
- `worldSession` aggregate state and `worldMap.selectedInspect` UI focus.
- Existing map drill/select API and state-patch application.

## 4. Target architecture

```text
Vue /works
  World Pulse       Tracked Quest HUD       Map / Key Clues
          \              |                 /
           +------ worldSession SSOT ------+
                          |
          HTTP aggregate / SSE / decision actions
                          |
               WorldInteractionService
                  (adapter/orchestration)
                    /       |       \
       QuestInteraction   Map      CommandRunner
          Projection     Service         |
              |                         commands
              |                  task state machine / Agent runtime
              v
  graph nodes + relationships + task ledgers + Agent run records
              |                         |
         world facts             account+Agent Memory
                    \--- governed refs ---/
```

Boundary rules:

1. `WorldInteractionService` orchestrates projections but does not implement Quest lifecycle or authorization.
2. A new task-domain read service builds the Quest interaction projection from authorized graph/task records.
3. Tracking, Objective focus, clue pinning, collaboration changes, Objective actions, Situation disposition, and Quest actions go through commands/services.
4. The frontend never synthesizes business progress, gate status, or policy results.
5. `worldSession` remains the only aggregate payload owner; child stores expose computed views rather than duplicated state.
6. World facts and explicit user selections live in the graph; STM/LTM stores conversation/episodic context and references graph objects without becoming their source of truth.
7. An object-sensitive Quest decision facade composes Quest governance and F16 Agent behavior decisions for human and Agent execution paths; each concrete command still performs final command authorization. These planes keep separate rule stores and decision records.

## 5. Backend implementation design

### 5.1 Ontology and persistence

Register relationship types:

| Relationship | From -> To | Purpose |
|---|---|---|
| `TRACKS_QUEST` | account -> quest | Explicit user-selected Quest; multiple active edges per account are allowed, with one edge per account+Quest pair. |
| `FOCUSES_ON` | account -> task/objective | Explicit current Objective within the tracked Quest; at most one active edge per account. |
| `PINS_CLUE` | account -> fact/observation/evidence | Explicitly retained, readable, materialized clue; R1 guarantees canonical `observation` targets. |
| `ASSISTED_BY` | quest -> npc_agent | Durable multi-Agent collaboration role and Companion identity. |

Selection transaction:

1. lock the account node;
2. authorize read access to every target and validate `HAS_OBJECTIVE` membership where applicable;
3. compare the caller's expected projection revision with the current revision;
4. for tracking, preserve other active Quest edges and reject/idempotently return an existing account+Quest edge; for focus, deactivate the replaced account-wide `FOCUSES_ON` edge;
5. insert the new edge with `selected_at`, `source`, actor, and correlation metadata;
6. emit an observable tracking/focus event without changing Quest or Objective lifecycle state.

Database enforcement complements the account-row lock: the existing active relationship uniqueness on source+target+type prevents duplicate `TRACKS_QUEST`; add a partial unique constraint on active `(source_id, type_code)` for `FOCUSES_ON`. If the selected schema cannot express a type-filtered partial index portably, introduce an equivalent current-selection row guarded by `FOR UPDATE` while keeping the graph edge as the semantic record; application-only last-write-wins is insufficient.

`PINS_CLUE` is created only for a materialized and readable fact/observation/evidence node. R1 registers `observation` with immutable assertion/source/provenance/observed-at/actor fields and initial unverified status; later Evidence records verify or challenge it without replacing the original observation. Unresolved semantic refs remain read-only Journal leaves. `ASSISTED_BY` stores role/lifecycle metadata (`role`, `status`, `is_primary_companion`, `capability_scope`, validity window, actor, correlation ID); it does not grant command authority or prove execution.

Do not store tracked Quest or focused Objective in `localStorage`, task attributes, or account `active_world` compatibility fields. Map hover/inspect remains ephemeral; account `location_id` remains the only current-room authority.

### 5.2 Quest interaction projection

Add a task-domain read service, proposed path:

`backend/app/services/task/quest_interaction_projection.py`

Input:

- database session;
- authenticated `Principal`;
- current location;
- display limits;
- optional requested/tracked Quest.

Output:

```json
{
  "contractVersion": "quest-interaction.v1",
  "capabilities": ["multi_quest_tracking", "durable_focus", "observation_clues", "quest_graph", "structured_conversation", "world_feedback"],
  "projectionRevision": "account-monotonic-opaque-revision",
  "lastEventId": "evt-991",
  "foregroundQuestId": "77",
  "trackedQuests": [{
    "id": "77",
    "title": "Restore safe AHU operation",
    "state": "executing",
    "riskLevel": "high",
    "tracking": "explicit",
    "situation": {
      "id": "75",
      "assertion": "...",
      "triggerKind": "mixed",
      "confidence": 0.92,
      "primarySubjectRef": "501",
      "relatedEntityRefs": ["501", "601"],
      "scopedAtRef": "42"
    },
    "goal": {"id": "76", "desiredState": "..."},
    "objectives": [],
    "recommendedObjectiveId": "80",
    "focusedObjectiveId": "80",
    "progress": {
      "totalObjectives": 3,
      "terminalObjectives": 1,
      "succeededObjectives": 1,
      "failedObjectives": 0,
      "displayStage": "in_progress"
    },
    "companion": null,
    "governance": {},
    "actions": []
  }],
  "questJournal": {"nodes": [], "edges": [], "unresolvedRefs": []},
  "worldPulse": [],
  "worldFeedback": []
}
```

Projection constraints:

- reuse `_can_read_semantic_node`/task visibility rules;
- derive progress from `HAS_OBJECTIVE` plus task state, never the current Objective alone;
- select recommended Objective deterministically from actionable state, risk/deadline, dependency readiness, and current location;
- return all readable explicit `TRACKS_QUEST` entries; resolve the single foreground Quest from the account-wide `FOCUSES_ON` target, with the most recently tracked readable Quest used only as a non-persisted display default when no focus exists;
- keep recommendation and explicit focus as separate fields;
- build a permission-filtered, bounded Quest subgraph containing Situation, Goal, Objectives, materialized observations/facts/evidence, collaboration Agents, and user selection edges; render task/Agent action and outcome records as a timeline overlay unless a domain contract has materialized them as graph objects;
- cap Journal/Pulse/Feedback lists server-side and expose cursors for later pagination;
- advertise a stable contract version/capability list;
- issue an opaque, account-scoped monotonic server projection revision and last visible event ID suitable for optimistic concurrency; every successful mutation affecting that account's authoritative location/Map semantics, visible Quest/Journal/Pulse/Feedback/collaboration/thread binding advances the revision, and a frontend counter is never authoritative.

Every mutation body or command adapter carries `expectedProjectionRevision`, optional `lastEventId`, and `idempotencyKey`. A mismatch returns `stale_projection` with refresh metadata and never replays a side effect automatically. Unknown capabilities are ignored; an unknown contract major falls back to the legacy task-only projection or an explicit unsupported state.

Persist revision state in a shared account-scoped record such as `world_interaction_revisions(account_node_id PK, revision BIGINT, last_event_id, updated_at)`. The mutation transaction locks this row, compares the expected revision, performs the domain write/outbox append, and increments revision before commit. External or asynchronous facts that change the visible projection advance it through the same helper when their domain event is applied. The API encodes the monotonic value as an opaque string; clients may compare equality only.

### 5.3 Protocol-neutral commands

Extend the Quest command family:

| Command | Behavior |
|---|---|
| `quest track <id> --if-revision <revision>` | Add an idempotent active `TRACKS_QUEST` edge without replacing other tracked Quests. |
| `quest untrack <id> --if-revision <revision>` | Deactivate only the matching Quest tracking edge without changing Quest state or other tracked Quests; clear an Objective focus inside that Quest in the same transaction. |
| `quest focus-objective <quest_id> <task_id> --if-revision <revision>` | Replace the caller's `FOCUSES_ON` edge after validating membership, visibility, and concurrency. |
| `quest pin-clue <quest_id> <node_id> --if-revision <revision>` | Create `PINS_CLUE` for a readable materialized fact/observation/evidence node. |
| `quest unpin-clue <quest_id> <node_id> --if-revision <revision>` | Deactivate the caller's matching clue edge. |
| `quest collaborator add/remove/update ... --if-revision <revision>` | Govern `ASSISTED_BY` role and lifecycle through authorized service logic. |
| `situation seen <id> --if-revision <revision>` | Record per-user seen state. |
| `situation snooze <id> --until <time> --if-revision <revision>` | Suppress from default World Pulse until expiry. |
| `situation dismiss <id> --reason <text> --if-revision <revision>` | Governed business disposition; never equivalent to UI hide. |

Tracking, focus, clue pinning, and collaboration commands require an idempotency key and return the new projection revision/event ID. None may imply claim/start/complete/approve, and none may mutate account `location_id`.

### 5.4 DecisionOption v2

Maintain backward compatibility while adding:

```typescript
interface DecisionOptionV2 {
  id: string
  actionType: string
  labelKey: string
  labelParams?: Record<string, string | number>
  label?: string
  consequenceKind?: 'confirmed' | 'predicted' | 'proposed'
  consequenceSummary?: string
  consequenceProvenanceRefs?: string[]
  consequenceConfidence?: number
  riskLevel?: 'low' | 'normal' | 'high' | 'critical'
  gateStatus?: 'clear' | 'approval_required' | 'blocked' | 'evidence_required'
  requiredEvidenceRefs?: string[]
  reversible?: boolean
  affectedEntityRefs?: string[]
  requiresConfirmation: boolean
}
```

The server computes these fields. The frontend may choose presentation but may not downgrade `requiresConfirmation`, `gateStatus`, risk, or consequence truth status. `predicted` requires provenance and confidence; `proposed` uses future/conditional copy; only deterministic facts/simulation may use `confirmed`.

### 5.5 Structured Quest conversation context

Extend `DecisionQueryRequest` and SSE request body:

```json
{
  "query": "What should I do next?",
  "mode": "aico",
  "thread_id": "...",
  "quest_context": {
    "quest_id": "77",
    "situation_id": "75",
    "goal_id": "76",
    "objective_id": "80",
    "focused_entity_id": "501",
    "projection_revision": "...",
    "last_event_id": "evt-991"
  }
}
```

Backend resolution:

1. parse IDs only as untrusted references;
2. rebuild `Principal` from the authenticated user;
3. authorize Quest, Situation, Goal, Objective, and focused entity independently;
4. verify graph membership (`RESPONDS_TO`, `PURSUES`, `HAS_OBJECTIVE`);
5. load pinned governance refs and visible Evidence summaries;
6. compare the opaque projection revision and last visible event ID; mark stale context or return a refresh-required stream event;
7. inject a structured, size-bounded Quest snapshot into Agent runtime metadata;
8. never use client summaries or prompt text as authorization facts.

`CommandRunOptions` should carry a typed context object into `CommandContext.metadata`. The AICO profile/worker converts the authorized snapshot into model context alongside the existing world snapshot.

The existing Memory contract remains authoritative: Mode A storage scope stays `account + transport_session + agent + conversation_thread`. Keep the existing thread `agent_node_id` as the actual speaking/runtime Agent and extend the directory with immutable `quest_node_id`, optional `collaboration_relationship_id`, creation revision, archive status/reason, and optional graph refs. Do not add a duplicate `companion_agent_node_id`. Switching Quest or actual Agent creates a new thread; it must not mutate or silently reuse the old binding.

On Quest completion/close or explicit collaboration end, the backend archives the thread into the Quest Journal and enqueues eligible raw/episodic content for account+Agent LTM promotion. Memory Thread + STM/LTM remains the transcript source of truth; `world_conversation_archive` is a compatibility read projection and logout is not the Quest archive trigger. Promotion preserves thread, Quest, Agent, graph refs, source revision, and retention policy. It never writes world facts or Agent configuration directly; organization-level changes require a governed LearningProposal.

### 5.6 Companion resolution

Resolution order:

1. visible, active, authorized primary `ASSISTED_BY` collaboration;
2. authorized Objective executor/supervisor Agent explicitly eligible for guidance;
3. configured system AICO fallback, labelled as a system guide rather than a world NPC.

Projection includes collaboration relationship ID plus Agent node ID, display name, role, location, availability, capabilities, validity, and authority summary. Multiple collaborators appear in Journal; one eligible primary Companion is selected deterministically. Agent location affects presentation, not read authorization. Collaboration never bypasses the central Policy decision or command authorization.

### 5.7 World Feedback and automation audit

R1 can build a compact stream from existing records; the new automatic execution path itself lands in R2:

- `task_state_transitions` for state changes and actor identity;
- `task_runs` for commands/tools, result summaries, Evidence refs, correlation/trace IDs;
- `task_events` for observable domain events;
- `agent_run_records` for Agent execution summaries where linked by correlation ID.

Required automatic execution record:

```text
trigger provenance
+ pinned policy/process versions
+ actor Agent principal
+ command/tool summary
+ state transition
+ result/evidence summary
+ correlation_id / trace_id / timestamps
```

Automatic success is informational. Failure, policy denial, missing evidence, low-confidence escalation, or kill-switch activation produces a World Pulse item eligible for human tracking.

### 5.8 World Pulse lifecycle

Separate UI attention from business state:

- `seen`: per-user attention state;
- `snoozed`: per-user suppression with expiry;
- `dismissed`: governed Situation disposition with actor/reason;
- `resolved`: derived from authoritative Situation/Quest outcome only.

Remove any UI action that hides all events while presenting itself as “clear resolved”.

Pulse facts remain derived from authoritative Situation/Quest state and event records. Add a dedicated `situation_attention` record keyed by account+Situation for high-churn `seen_at`, `snoozed_until`, and UI dismissal timestamps; do not copy the full Pulse item into a second business SSOT. Governed Situation disposition actor/reason remains in the Situation command/event path, not the attention table.

Minimum columns are `account_node_id`, `situation_node_id`, `seen_at`, `snoozed_until`, `ui_dismissed_at`, `updated_at`, and `revision`; account+Situation is unique. Snooze expiry changes read filtering without changing Situation state. A business dismiss/resolve command writes the Situation transition/event and may clear obsolete attention in the same transaction, but the attention row never proves business resolution.

### 5.9 Three-plane policy composition and automatic execution

Introduce a task-domain Quest decision facade that accepts actor/Agent, Quest, Objective, target objects, proposed command/action, risk, pinned Policy/Process versions, Evidence requirements, and projection revision. It composes three explicit planes: Quest governance/object evaluation, F16 Agent behavior `PolicyEngine` when an Agent is involved, and existing command authorization at execution time. Each plane retains its own rule source and decision record; the facade returns the conservative combined allow/deny/approval/evidence/escalation result with reason codes, expiry/revision, and correlation ID.

- Existing command authorization remains the final mandatory check for every actual command and is never cached across a mutation boundary.
- Human UI, Companion proposals, Planner, and automatic execution consume the same decision contract; none implements a private policy bypass.
- Object-specific Agent configuration/Skill references inform capability matching but never grant blanket authority.
- R2 automatic execution uses an explicit orchestrator: evaluate -> materialize/bind Objective when required -> invoke existing command/service as the Agent principal -> write task transition/run/event and Agent run records -> collect Evidence/result -> verify or escalate.
- Fully model-generated execution topology is deferred. The first implementation executes only registered actions/process capabilities with deterministic limits, idempotency, timeout, cancellation, and kill-switch handling.

### 5.10 Quest Journal graph projection

The first release returns a bounded, permission-filtered graph rooted at the selected Quest:

- nodes: Situation, Goal, Quest, Objectives, materialized Fact/Observation/Evidence, collaborating Agents, and materialized Outcome/Learning objects;
- edges: authoritative semantic relationships such as `RESPONDS_TO`, `PURSUES`, `HAS_OBJECTIVE`, `BASED_ON_FACT`, `SUPPORTED_BY`, `SCOPED_AT`, `ASSISTED_BY`, `TRACKS_QUEST`, `FOCUSES_ON`, and `PINS_CLUE`;
- unresolved pinned refs: typed leaf descriptors with source and version, clearly marked non-node/non-verified;
- timeline overlay: task transitions, command/Agent runs, policy decisions, and result records remain available as a temporal view of the same Quest and are not synthesized into graph nodes/edges unless another domain contract explicitly materializes them.

Traversal is allowlisted, depth- and count-bounded, and authorized per node/edge. This is not a general graph editor and may not expose hidden neighbors through counts, labels, or dangling edge IDs.

### 5.11 Governed Agent learning handoff

Quest Outcome, Evidence, human feedback, archived dialogue, and World Feedback can feed account+Agent episodic/LTM promotion. A separate governed learning path may propose changes to Process/SOP/Skill, capabilities, or Agent configuration. Only an approved LearningProposal may create a new version and an authorized command may attach it to an Agent node. Preserve the previous version and rollback metadata; never let a tick or LTM write update formal configuration directly.

## 6. Frontend implementation design

### 6.1 Types and state

Add stable types to `frontend/src/types/world.ts`:

- `QuestInteractionStatePayload`
- `QuestInteractionCapabilities`
- `TrackedQuest`
- `QuestObjectiveSummary`
- `QuestProgressProjection`
- `WorldPulseItem`
- `WorldFeedbackItem`
- `QuestCompanion`
- `QuestConversationContext`
- `QuestJournalGraph`
- `QuestJournalNode` / `QuestJournalEdge` / `UnresolvedSemanticRef`
- extended `DecisionOption`

`WorldInteractionState` owns `quest_interaction`. `decisionCenter`, `worldMap`, and a new read-only `questJournal` store/composable expose computed views; they do not copy payload data.

### 6.2 Component migration

Introduce domain-named components:

| Component | Responsibility |
|---|---|
| `WorldPulse.vue` | Situation discovery, attention state, track/snooze/dismiss actions. |
| `TrackedQuestHud.vue` | Quest, Goal, current Objective, gate, and world-action prompt. |
| `QuestJournal.vue` | Permission-filtered Quest relationship graph plus temporal history view. |
| `CompanionEncounter.vue` | Companion identity, dialogue choices, streaming response, follow-up input. |
| `WorldFeedback.vue` | Human/Agent action outcomes and Evidence status. |
| `ChoiceConsequence.vue` | Consequence/risk/gate/evidence preview and confirmation. |

Migration strategy:

- keep `DecisionCenterFlow` as the orchestration shell initially;
- move behavior out of `ActiveTaskCard` and `DecisionEventCard` incrementally;
- retain compatibility rendering for legacy task-only items;
- remove obsolete naming only after tests and routing references migrate.

### 6.3 Interaction rules

- Tracking a Quest is an explicit user action; recommendation is visually distinct.
- Focusing an Objective and pinning a materialized Clue are explicit commands; the UI updates only after command success and a new projection revision.
- Selecting a Pulse item highlights `relatedEntityRefs`; tracking it changes HUD only after command success.
- Selecting a Quest entity uses semantic-map select/drill and never changes `location_id`.
- Companion choices send structured Quest context and open the Quest-scoped dialogue.
- Choosing a world action first renders consequence/gate information when material, then executes the returned action ID.
- State patches refresh Quest, Map, Key Clues, Pulse, and Feedback from one aggregate revision.
- A stale-state response refreshes the aggregate and asks the user to confirm again; it never retries a mutating action automatically.
- Journal renders confirmed graph objects differently from unresolved refs and from Agent/model predictions.
- On mobile, Map remains the canvas; active Quest/Objective/action use a responsive HUD, while Journal, Key Clues, and Companion open as non-destructive layers.

### 6.4 Localization and accessibility

- Render `labelKey + labelParams`; use server `label` only as fallback.
- Announce Quest updates and new critical Pulse items through an ARIA live region.
- Move keyboard focus predictably when opening the Journal, consequence confirmation, or Companion dialogue.
- Risk, gate, route, and status must use text/icon/shape in addition to color.
- Respect reduced-motion preferences for map/Quest update effects.
- Preserve readable text and controls at 200% zoom and narrow mobile widths.

## 7. Delivery plan

### Phase 0 — Contract and status correction（G0 complete）

- Mark F03 as approved for implementation while retaining G1–G4 activation gates.
- Record R1/R2/R3/R4 delivery mapping and explicit capability labels in stable F03/F06.
- Align F02/F06/F12/F16 terminology and remove contradictory acceptance claims.
- Freeze `TRACKS_QUEST / FOCUSES_ON / PINS_CLUE / ASSISTED_BY`, minimal Observation, Memory binding, three-plane policy composition, request/response schemas, mutation envelope, and migration compatibility.

Exit gate G0:

- [x] stable docs agree on terminology, release scope, and ownership;
- [x] SPEC layout validation passes except documented pre-existing exceptions;
- [x] API/type contract and C01–C13 review approved for implementation.

### Phase 1 — Authoritative Quest projection and tracking

- Register `TRACKS_QUEST`, `FOCUSES_ON`, `PINS_CLUE`, and `ASSISTED_BY` relationship types.
- Register the minimal canonical `observation` node and provenance schema used by R1 Clue pins.
- Implement track/untrack, focus, clue pin/unpin, and collaboration service/command paths.
- Add Quest interaction projection with complete Objective aggregates.
- Add the bounded, authorized Quest Journal relationship graph and unresolved-ref leaves.
- Add multi-entity Situation projection and state version.
- Replace synthetic progress and queue-first active selection.
- Integrate projection into `GET /world-sessions/current` and refresh endpoint.
- Advertise contract version/capabilities and return opaque projection revision + last event ID.

Exit gate G1:

- multiple explicit tracked Quests survive refresh independently and respect visibility; untracking one preserves the others;
- Objective focus and materialized Clue pins survive refresh without changing Objective state;
- no tracked Quest falls back to recommendation without silently persisting it;
- Objective aggregate equals `show_quest` for the same Quest;
- Journal reveals no unauthorized neighbor metadata and marks unresolved refs;
- map focus does not modify location or tracking state.

### Phase 2 — Companion and governed choices

- Add structured Quest conversation request/context resolution.
- Add immutable Quest/collaboration metadata and backend archive lifecycle to existing Memory threads while preserving `agent_node_id` as the actual Agent identity.
- Resolve and render Companion identity.
- Extend DecisionOption and localization contract.
- Implement `confirmed / predicted / proposed` consequence semantics.
- Add consequence/gate confirmation UI.
- Add the three-plane Quest decision facade while retaining F16 behavior-policy and command-authorization boundaries.

Exit gate G2:

- tampered Quest/Objective/entity refs are rejected or omitted without data leakage;
- stale context produces refresh-required behavior;
- policy-blocked actions cannot execute from UI or direct API;
- every user-visible action localizes through stable keys;
- Companion speaker identity is preserved in conversation/archive records.
- archived Quest conversation is eligible for scoped episodic/LTM promotion but cannot directly update world facts or Agent configuration.

### Phase 3 — World Pulse and World Feedback

- Project Situation-based Pulse items instead of task-only events.
- Implement seen/snooze/dismiss commands and read filtering.
- Add account+Situation `situation_attention` persistence for seen/snooze/UI-dismiss attention state.
- Project task/Agent automation records into World Feedback.
- Implement the explicit automatic-execution orchestrator over registered commands/process capabilities.
- Escalate automatic failures and governance exceptions into Pulse.
- Add cursor pagination and display caps.

Exit gate G3:

- automatic success is visible in Feedback without entering the human action queue;
- automatic failure produces an actionable Pulse item;
- every automatic action carries the central policy decision, Agent principal, command/run evidence, and correlation chain;
- seen/snoozed/dismissed/resolved semantics are distinct and audited;
- no local-only “clear resolved” behavior remains.

### Phase 4 — Game-native UI completion

- Split shell into World Pulse, Tracked Quest HUD, Journal, Companion, and Feedback components.
- Complete Map/Quest/Key Clues bidirectional interaction.
- Implement Map-canvas mobile HUD/layers and accessibility behavior.
- Retain legacy Objective compatibility fallback.
- Perform authenticated visual and interaction QA.

Exit gate G4:

- keyboard, screen reader, zoom, contrast, and reduced-motion checks pass;
- mobile and desktop interaction follow the same command/gate semantics;
- no Inbox/Kanban/KPI Dashboard or independent generic assistant is the primary `/works` metaphor;
- user testing confirms Situation -> Quest -> world action -> feedback is understandable without task-system terminology;
- at least 80% of test users orient within 30 seconds, at least 90% complete one governed action without facilitation, authorization confusion is at most 5%, stale recovery succeeds at least 95%, critical-path keyboard coverage is 100%, and sampled screen-reader task completion is at least 90%.

### Phase 5 — Evidence verification and Learning Review (R3/R4)

- Materialize Evidence/verification/outcome/learning objects from F06.
- Add Evidence exploration and quality-gate result presentation.
- Add LearningProposal review without allowing Agent self-publication.
- Apply approved learning versions to Agent Skill/capability/policy-profile references through controlled commands with rollback metadata.
- Replace remaining summary refs with graph-backed nodes where available.

## 8. File-level change map

### Backend

| Path | Planned work |
|---|---|
| `backend/app/services/task/quest_interaction_projection.py` | New authorized read projection. |
| `backend/app/services/task/quest_semantic_service.py` | Reuse/refactor Quest loading and aggregate helpers. |
| `backend/app/services/task/quest_policy_decision.py` | Compose Quest governance and F16 behavior decisions; expose a structured result while command authorization remains final. |
| `backend/app/services/task/quest_automation_orchestrator.py` | Explicit registered-action automatic execution, audit, Evidence, and escalation flow. |
| `backend/app/commands/game/task/semantic_commands.py` | Track/untrack/focus, clue pinning, collaboration, and Situation attention commands. |
| `backend/app/services/world_interaction/service.py` | Consume projection; remove inline Quest projection and queue-first selection. |
| `backend/app/services/world_interaction/aico_stream_query.py` | Carry authorized Quest context and Quest/actual-Agent thread scope. |
| `backend/app/services/world_interaction/command_runner.py` | Add typed Quest context to command metadata. |
| `backend/app/api/v1/endpoints/world_interaction.py` | Request schema and adapter wiring only. |
| `backend/app/models/system/agent_memory_tables.py` | Add immutable Quest/collaboration binding and archive metadata while reusing existing `agent_node_id`. |
| `backend/app/game_engine/agent_runtime/conversation_stm_service.py` | Enforce thread binding and enqueue governed episodic/LTM handoff. |
| `backend/db/schema_migrations.py` | Register `observation`/relationship types, `situation_attention`, revision persistence, and required uniqueness/concurrency indexes. |
| `backend/db/schemas/database_schema.sql` | Keep canonical schema definitions synchronized when tables/indexes change. |

### Frontend

| Path | Planned work |
|---|---|
| `frontend/src/types/world.ts` | Capability/revision, Quest graph, Pulse/Feedback/Conversation/DecisionOption contracts. |
| `frontend/src/api/decisionCenter.ts` | Structured Quest SSE request and events. |
| `frontend/src/api/worldSessions.ts` | Aggregate Quest interaction types/actions. |
| `frontend/src/stores/worldSession.ts` | Apply versioned aggregate/state patches. |
| `frontend/src/stores/decisionCenter.ts` | Compatibility computed views; no copied state. |
| `frontend/src/components/decision/` | New game-native components and legacy migration. |
| `frontend/src/components/context/ContextSummaryPanel.vue` | Key Clues projection from shared focus. |
| `frontend/src/stores/worldMap.ts` | Multi-entity highlight and route interaction. |
| `frontend/src/locales/{zh,en}.ts` | Stable action keys and Quest language. |

## 9. Test plan

### 9.1 Backend unit tests

- selection transactions: multi-track add/idempotency/selective untrack, account-wide focus replace/clear, pin, stale revision, inactive or unauthorized target;
- collaboration: multi-Agent roles, primary resolution, lifecycle, and no implied execution authority;
- projection: capabilities/revision, explicit/recommended tracking, multi-Objective ordering, blockers, aggregate progress, caps;
- Journal graph: allowlisted depth/size, per-node/edge authorization, unresolved refs, and no hidden-neighbor leakage;
- Situation entity refs: primary, related, scoped location, unresolved refs;
- DecisionOption v2: localization keys, gates, consequence truth/provenance/confidence, evidence, reversibility;
- Companion resolution and fallback;
- World Feedback mapping from human and Agent actors;
- Pulse attention lifecycle and expiry;
- structured Quest context authorization and stale revision behavior;
- policy facade object inputs, separate Quest/F16/command decisions, conservative composition, expiry/revision, and command-authorization enforcement;
- automatic orchestrator success/failure/timeout/idempotency/kill-switch/escalation records;
- Quest thread immutable binding, archive, LTM handoff metadata, and no direct config mutation.

### 9.2 Backend API and contract tests

- current/refresh interaction payload schema, contract capabilities, revision, and Journal graph;
- SSE Quest context propagation, cancellation, stale context, and state patch;
- tampered cross-owner Quest/Situation/Objective/entity references;
- decision action cannot bypass task state machine or Policy gate;
- command/API parity for track/untrack/focus/pin/collaboration and Situation disposition;
- English-only backend log templates.

### 9.3 PostgreSQL integration tests

- concurrent tracking preserves multiple distinct Quest edges, prevents duplicate active account+Quest edges, and leaves one active `FOCUSES_ON` edge per account;
- `PINS_CLUE` accepts readable canonical observations and rejects unresolved/unauthorized targets; `ASSISTED_BY` preserves multiple role-scoped collaborators;
- account-scoped projection revision advances monotonically and stale mutations cannot produce side effects;
- `situation_attention` is isolated per account and does not alter authoritative Situation state;
- relationship type registration and trait sync;
- projection visibility with owner/admin/pool/Agent principals;
- Agent automatic action writes transition/run/event records atomically enough for Feedback projection;
- correlation/trace joins between task and Agent records.

### 9.4 Frontend unit/component tests

- worldSession applies versioned Quest patches without duplicating state;
- Tracked Quest and recommendation render differently;
- Journal renders the authorized relationship graph, unresolved refs, multiple Objectives, collaborators, and fact/evidence nodes;
- Objective focus executes the business-context command without mutating Objective lifecycle state;
- map selection highlights related Quest and Pulse entities;
- Companion request contains structured context and correct Quest thread;
- Companion/Quest switch creates a new bound thread; archive stays visible and becomes eligible learning input;
- consequence modal blocks/approves the correct action ID;
- World Feedback distinguishes human, Agent, success, failure, and escalation;
- legacy task-only fallback remains operable;
- zh/en key completeness and backend label fallback.

### 9.5 Accessibility and responsive tests

- keyboard-only tracking, map locate, dialogue, confirmation, and Journal navigation;
- screen-reader labels and live Quest update announcements;
- 200% zoom and 320px-width layout;
- non-color risk/gate distinction and contrast;
- reduced-motion mode;
- focus restoration after dialog close and state refresh.

### 9.6 Authenticated end-to-end scenario

1. Agent observation raises a multi-entity Situation.
2. World Pulse highlights the device and room on Map.
3. User explicitly tracks the recommended Quest.
4. User focuses an Objective; the relation persists without claiming or starting it, and Journal shows the authoritative Quest subgraph and collaborators.
5. User asks why the Objective exists; structured context is authorized server-side.
6. Companion points to a world entity and offers a governed choice.
7. User reviews consequence and starts the Objective.
8. Agent automatically performs an authorized sub-action; Feedback records it.
9. Automatic evidence is insufficient, creating a human Pulse escalation.
10. User supplies/requests evidence and completes the Objective.
11. Quest enters verification; UI does not claim Goal satisfaction before acceptance.
12. Quest conversation archives with graph references and enters scoped learning input; no Agent configuration changes without an approved LearningProposal.

### 9.7 Minimum commands

Run focused tests first, then broaden at each gate:

```bash
cd backend && conda run -n campusworld pytest tests/services/test_user_task_queue_mapping.py tests/services/test_quest_semantic_service.py
cd backend && conda run -n campusworld pytest tests/api/test_world_interaction_endpoints.py
cd backend && conda run -n campusworld pytest -m postgres_integration
cd frontend && npm run type-check
cd frontend && npm run test -- --run
cd frontend && npm run build
cd backend && python scripts/validate_spec_layout.py
```

Add focused test files as implementation lands; do not defer all coverage to the final phase.

## 10. Rollout and compatibility

- Add response fields; do not remove `activeTask`, legacy `label`, or task-only rendering in the first release.
- Gate the new Quest projection behind explicit backend contract version/capabilities, not incidental field presence or frontend hard-coded environment flags.
- Read old Quest nodes without tracking/companion edges using recommendation and system-guide fallbacks.
- Treat missing focus/clue/collaboration edges as absent semantics; never backfill them from model inference.
- Do not backfill synthetic progress into Quest attributes.
- Enable structured Quest context before removing prompt-only context.
- Retire legacy fields only after one release with contract tests and client telemetry confirming no consumers.

## 11. Observability

Track:

- projection latency and item counts;
- explicit track/untrack events;
- focus/pin/collaboration change events and optimistic-conflict rate;
- recommendation-to-track conversion;
- stale-context refreshes;
- Journal graph size, truncation, unresolved-ref, and authorization-filter counts;
- policy/gate denials by action type;
- Companion fallback rate;
- Agent automatic success/failure/escalation counts;
- Quest conversation archive-to-memory promotion lag and governed-learning approval/rejection counts;
- Feedback projection lag;
- SSE cancellation and failure rate.

Logs remain English-only and contain IDs/correlation metadata, not confidential Evidence content or model chain-of-thought.

## 12. Definition of done

F03 is approved for implementation and may move to active only when G1–G4 pass and:

- multiple tracked Quests are explicit, independently removable, and never an unexplained queue-first choice; the foreground HUD Quest follows the single focused Objective or a clearly labelled read-only default;
- explicit Quest, Objective, and Clue selections are graph-persisted and auditable while transient map exploration stays ephemeral;
- Quest progress is authoritative and its basis is visible;
- the Journal renders a bounded authorized Quest relationship graph in the first release;
- persistent multi-Agent collaboration, Companion identity, thread binding, and structured context are authorized and auditable;
- choices distinguish confirmed, predicted, and proposed consequences and expose material gate/evidence information;
- the Quest governance, F16 behavior-policy, and final command-authorization planes are separately auditable, conservatively composed, and preserved by the explicit automatic executor;
- Agent automatic work is visible through World Feedback;
- archived Quest dialogue can feed scoped Memory, while formal Agent configuration changes require approved learning and controlled commands;
- Map, World Pulse, Quest, Companion, and Key Clues share one versioned interaction state;
- business actions remain protocol-neutral and policy-gated;
- at least 80% of users orient within 30 seconds, at least 90% complete a governed action unaided, authorization confusion is at most 5%, stale recovery is at least 95%, critical-path keyboard coverage is 100%, and sampled screen-reader task completion is at least 90%;
- frontend type-check, focused/full tests, backend unit/API/integration tests, build, and authenticated interaction QA pass.
