ANALYSIS_TEMPLATE = """
You are the analysis layer for Prompt Architect. The target category is: {target_category}.
Extract the user's actual intent from the raw input into a specification that
another developer can use to produce a complete implementation prompt.

Do not silently add an unrequested requirement, constraint, technology,
deliverable, or preference. However, explicitly identify important
implementation decisions that are genuinely absent from the input in
assumptions or unknowns. This can include the platform, frontend/backend
stack, database, authentication, payment provider, hosting, deployment model,
testing approach, and non-functional requirements when they are relevant to
the target category.

Critical classification rule: first scan the raw input for explicit decisions.
If the user names a frontend technology, backend technology, database,
authentication provider, payment provider, hosting provider, language,
framework, library, or deployment choice, treat that decision as confirmed
user input. Preserve it in requirements, preferences, or constraints as
appropriate. Never describe an explicitly named choice as "not confirmed",
"unknown", or an assumption, and do not ask a clarifying question about it.
For example, if the user says "React frontend, Django backend, and
PostgreSQL database", those are confirmed choices and must not appear in
assumptions or unknowns.

Also detect explicit deferrals, exclusions, and refusals. Phrases such as
"not right now", "later", "defer this", "do not implement", "out of scope",
"not needed", or "I will decide later" are intentional user decisions.
Represent them as constraints or exclusions, and do not turn them into
assumptions, unknowns, proposed defaults, or recommendations. For example,
if the user says payment integration is not needed right now, preserve that
as a current out-of-scope constraint; do not choose Stripe or ask the user to
select a payment provider. The same rule applies to deployment, hosting,
authentication, and any other technical decision.

Only place a decision in assumptions when the raw input does not specify it
and the system needs a provisional interpretation, unless the user has
explicitly deferred or excluded that decision. An assumption must describe
the provisional interpretation, not claim that an explicit user decision is
unconfirmed. An unknown should be phrased as a high-value question only when
the answer would materially change the implementation and the user has not
already deferred the decision. Do not put missing decisions in requirements.

Extract:
- the concrete goal;
- stated or clearly implied requirements;
- stated preferences;
- hard constraints and exclusions;
- assumptions that need to be made explicit;
- at most four high-value unknowns, ranked 1 (highest) to 5.

Every direct choice explicitly stated by the user must be retained as a
confirmed requirement, preference, or constraint. This includes named
frontend/backend frameworks, databases, authentication methods, payment
providers, hosting, and deployment choices. Every explicit deferral must be
retained as a constraint or exclusion.

Before returning the JSON, compare every assumption and unknown against the
raw input. Remove any item whose decision is explicitly stated by the user.
Do not output assumptions such as "the backend stack is not confirmed" when
the raw input names a backend stack.
Remove any proposed provider, deployment model, or technical default that
conflicts with an explicit deferral or exclusion. Preserve the deferral in
constraints so the generation step can enforce it.

Return only the requested structured JSON object.

RAW INPUT:
{raw_input}
"""

STRICT_ANALYSIS_SUFFIX = """
Your previous response was invalid. Return only valid JSON matching every
required field and type. Use [] when a list has no items. Do not use markdown
fences.
"""

QUESTION_TEMPLATE = """
You are selecting the next clarification question for Prompt Architect.
Ask exactly one concise, high-value question that materially improves the
implementation prompt for the target category: {target_category}.

The user has already provided the raw idea and may have answered or skipped
earlier questions. Do not repeat a question. Do not ask about a decision the
user explicitly deferred or excluded. Do not ask for information already
present in the specification or clarification history. The question should
be answerable in one or two sentences.

RAW IDEA:
{raw_input}

CURRENT SPECIFICATION:
{spec}

CLARIFICATION HISTORY:
{history}

Return only JSON with one field: question.
"""

ASSUMPTIONS_TEMPLATE = """
Complete the Prompt Architect specification using the user's clarification
history. Return the full updated specification, not commentary.

Precedence:
1. Explicit user constraints, exclusions, and deferrals.
2. Direct user answers.
3. Clearly implied information from the raw idea.
4. Reasonable AI assumptions for remaining gaps.
5. Unknowns only when a decision cannot be safely assumed.

Answers with provenance `confirmed` are user decisions and must be reflected
in the resulting confirmed specification. Answers marked `ai_assumption` are
questions the user asked Prompt Architect to answer; resolve them with a
bounded assumption rather than treating them as unresolved. Never
choose a payment provider, hosting provider,
deployment model, or other vendor-specific technology unless the user
confirmed it or it already exists as an assumption in the specification.
Preserve explicit "later", "not now", "deferred", and "out of scope"
decisions in constraints. Do not include more than four unknowns.

For each assumption, include the assumption text in `assumptions` and record
matching provenance in `assumption_provenance` as an object with `text` and
`source`. Use `ai_assumption` for assumptions introduced while completing the
specification. Do not label direct user answers as assumptions.

RAW IDEA:
{raw_input}

TARGET CATEGORY:
{target_category}

CURRENT SPECIFICATION:
{spec}

CLARIFICATION HISTORY:
{history}

Return only JSON matching the required specification schema.
"""

MERGE_TEMPLATE = """
Merge the user's custom requirements into this existing specification. Do not
invent anything and do not duplicate existing items. If a custom requirement
conflicts with an inferred preference or constraint, keep it in an added list
and describe the conflict in conflicts.

EXISTING SPEC:
{spec}

CUSTOM REQUIREMENTS:
{custom_requirements}

Return only JSON with added_preferences, added_constraints, and conflicts.
"""

GENERATION_TEMPLATE = """
Generate a complete, standalone, copy-paste-ready Markdown implementation
prompt using only the confirmed specification below. The result will be
pasted directly into an AI coding, design, or planning tool by a developer.
It must tell that tool what to build, how to structure the work, and what
conditions define completion. Do not return a short requirements summary.

The confirmed specification is the contract. Do not use or recover anything
from the original raw input that is absent from the specification.

Interpret clarification history using its provenance:
- `confirmed` answers are explicit user decisions and may inform confirmed
  requirements, preferences, or constraints.
- `ai_assumption` answers are provisional and must remain visibly labeled as
  assumptions in the final prompt.
- Items under `assumptions` are provisional AI decisions and must remain
  visibly labeled as assumptions in the final prompt.
- `assumption_provenance` identifies whether an assumption came from initial
  analysis (`ai_analysis`) or was introduced after clarification
  (`ai_assumption`). Preserve that distinction when presenting assumptions.
- Confirmed answers must not be moved into assumptions. Skipped answers must
  not be described as confirmed requirements.

Missing technical decisions:
- Do not silently present an invented choice as user-approved.
- When the specification contains an explicit assumption about a missing
  decision, turn it into a clearly labeled "Proposed default" or
  "Implementation assumption" in the prompt.
- If no explicit assumption or user decision is present, do not choose a
  provider, deployment platform, hosting model, or other vendor-specific
  technology merely to make the prompt more concrete. If implementation
  cannot proceed without it, include a concise "Decisions to confirm"
  section that names the unresolved decision without recommending a provider.
  If the specification says the decision is deferred, excluded, or not
  needed yet, preserve that wording as a current out-of-scope item and do not
  include a "Decisions to confirm" item for it.
- For an unspecified web application, use this provisional baseline unless it
  conflicts with the specification: React + Vite for the frontend, Django +
  Django REST Framework for the backend, PostgreSQL for persistence, and
  environment-based configuration. Label this as a proposed stack, not as a
  confirmed user requirement. For a design-only request, propose the
  appropriate design artifact and handoff format instead of inventing a
  backend.
- Never introduce a payment provider, payment implementation, hosting
  provider, Docker/Docker Compose setup, or deployment model unless it is
  confirmed in the specification or explicitly listed as an assumption.
  In particular, do not convert a deferred payment or deployment decision
  into Stripe, Docker, or any other named default.
- Treat explicit authentication and stack choices exactly like payment and
  deployment choices: preserve named choices as confirmed, and preserve
  explicit deferrals without selecting replacements.
- Never add unrelated features, generic filler, or unrequested best practices.

The prompt should normally contain:
1. Role and objective.
2. Project context and target outcome.
3. Confirmed requirements and user constraints.
4. Implementation assumptions and proposed technical defaults, clearly
   separated from confirmed requirements.
5. Detailed scope and behavior.
6. Architecture or component boundaries appropriate to the target.
7. Data, API, state, validation, security, and error-handling details when
   relevant.
8. Responsive/accessibility/non-functional expectations when relevant.
9. Deliverables and an ordered implementation plan.
10. Acceptance criteria and explicit out-of-scope items.

Use precise language and concrete output instructions. A developer should be
able to copy the entire result into an implementation tool without needing to
rewrite it first. Keep it focused: do not repeat constraints or invent
requirements merely to make the prompt longer.

Target-specific content focus for {target_category}:
{category_focus}

CONFIRMED SPECIFICATION:
{spec}

Return only the final Markdown prompt.
"""

CATEGORY_FOCUS = {
    "general": "Produce a complete implementation brief while first stating the deliverable type and proposed platform/stack when absent. Cover objective, context, requirements, constraints, assumptions, deliverables, acceptance criteria, and out-of-scope work without pretending an unconfirmed technology choice is settled.",
    "design": "Produce a design-ready prompt focused on the visual system, information architecture, page and component inventory, user flows, interaction states, responsive behavior, accessibility, content hierarchy, and developer handoff artifacts. Do not invent backend behavior unless it is in the specification.",
    "frontend": "Produce a frontend implementation prompt covering the selected or proposed framework, route/page structure, component boundaries, state management, API integration contract, loading/error/empty states, form validation, interactions, responsive behavior, accessibility, testing expectations, and build deliverables.",
    "backend": "Produce a backend implementation prompt covering the selected or proposed runtime/framework, API endpoints/contracts, data model and migrations, authentication/authorization, validation, business logic, transaction/payment boundaries when relevant, error handling, security, testing, observability, and deployment deliverables.",
    "fullstack": "Clearly separate frontend, backend, database, authentication, external integrations, shared contracts, end-to-end flows, environment configuration, testing, and deployment. Include enough concrete architecture and acceptance criteria for a developer to implement the complete system.",
}
