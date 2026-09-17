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

Only place a decision in assumptions when the raw input does not specify it
and the system needs a provisional interpretation. An assumption must
describe the provisional interpretation, not claim that an explicit user
decision is unconfirmed. An unknown should be phrased as a high-value
question only when the answer would materially change the implementation.
Do not put missing decisions in requirements.

Extract:
- the concrete goal;
- stated or clearly implied requirements;
- stated preferences;
- hard constraints and exclusions;
- assumptions that need to be made explicit;
- at most four high-value unknowns, ranked 1 (highest) to 5.

Before returning the JSON, compare every assumption and unknown against the
raw input. Remove any item whose decision is explicitly stated by the user.
Do not output assumptions such as "the backend stack is not confirmed" when
the raw input names a backend stack.

Return only the requested structured JSON object.

RAW INPUT:
{raw_input}
"""

STRICT_ANALYSIS_SUFFIX = """
Your previous response was invalid. Return only valid JSON matching every
required field and type. Use [] when a list has no items. Do not use markdown
fences.
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

Missing technical decisions:
- Do not silently present an invented choice as user-approved.
- When the specification contains an explicit assumption about a missing
  decision, turn it into a clearly labeled "Proposed default" or
  "Implementation assumption" in the prompt.
- If no sensible default is present, include a concise "Decisions to confirm"
  section with a practical recommended default and explain that it is
  provisional. The implementation should still be concrete enough to begin.
- For an unspecified web application, use this provisional baseline unless it
  conflicts with the specification: React + Vite for the frontend, Django +
  Django REST Framework for the backend, PostgreSQL for persistence, and
  environment-based configuration. Label this as a proposed stack, not as a
  confirmed user requirement. For a design-only request, propose the
  appropriate design artifact and handoff format instead of inventing a
  backend.
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
