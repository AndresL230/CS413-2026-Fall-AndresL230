# AI-assisted work log: Assignment 3

Tool: Claude Code (Claude Opus 5.5), 2026-09-29. These are my important
prompts while working on the requirements specification, in order. For each
one: what I asked for, why, and what came of it.

## 1. "Lets get started on the assign 03"
The AI read the assignment and the stakeholder brief. It then asked me
whether I had any real answers from the instructor, since the assignment
forbids presenting an invented answer as a stakeholder decision. I had none
for the specific questions, so every gap in the document is recorded as a
labeled assumption or as unresolved.

## 2. "Before we do anything give me an overview of what were doing here"
I wanted to understand the assignment before any writing started. The AI
explained that the task is to pin down *what* the system should do, not to
build it. It summarized what the brief asks for, pointed out where the brief
is vague (for example "respond promptly" and "come back to their work"), and
listed each required section with its grading weight. I chose to write the
clarification questions and assumptions first and review them before any
requirements were written.

## 3. "1" (questions first)
The AI drafted eight clarification questions (Q1–Q8) with assumptions
(A1–A8). It pointed out the choices I should check most carefully: the
proposed numbers (10-second time limit, 15-minute setup, two actions to
switch examples), whether saving should include file export, and whether a
test should be able to expect a runtime error.

## 4. "Here are some more suggestions and ideas" (full draft)
I brought in a full draft of the specification built on those questions.

**Significant suggestions from the AI:**
- **Section 1:** a scope that separates the environment from the compiler,
  with in-scope, out-of-scope and deferred lists.
- **Section 3:** 19 functional and 5 quality requirements, using a
  Must/Should/Could priority scheme.
- **Proposed targets not in the brief:** 0.5-second responsiveness (QR3) and
  200% text size (FR19), both labeled as proposals.
- **Test reporting:** environment errors are counted separately from failed
  tests (FR17), so a compiler outage does not look like a compiler bug.
- **Section 4:** the interfaces, including a mock compiler that can simulate a
  program that never finishes.
- **Sections 5–7:** eight acceptance checks (four of them failure cases),
  the traceability table and the review notes.

**Corrections and decisions:**
- The AI suggested leaving out a "save current program as a test" feature
  because it is not in the brief. I agreed.
- Sharing (FR18) was set to Could, since the brief says the instructor could
  live without it.
- The AI flagged that stopping a collection run is not fully specified. I
  kept this as an unresolved issue rather than inventing an answer.

I asked the AI to check the draft for contradictions and gaps. It found:
- **A3/A6 vs. FR18:** the assumptions relied on exporting collections, but
  that feature was only Could.
- **AC1:** it expected a computed result (720) that the mock compiler cannot
  produce.
- **AC6:** it required the run itself to stop within 0.5 seconds, which is
  stricter than QR3.
- **Time limit:** it applied only to runs, not checks.
- **Several collections:** it was unclear whether a user could have more than
  one.
- **Small errors:** a traceability entry cited IF2 instead of A1, and AC4 used
  "unsaved" even though FR5 saves automatically.

The AI also warned that review notes describing issues from "an early draft"
must describe things that really happened, so notes it could not confirm
were replaced with the issues found in this review.

## 5. "I reviewed the output … put that into the REQUIREMENTS.md now"
The AI suggested raising FR18 to Should to fix the contradiction. I kept it
at Could. Instead, A3 and A6 were rewritten to say that moving or sharing
whole collections depends on FR18, and what happens if it is not delivered.
The other fixes were applied as listed above. A new assumption, A9 (a user
may keep several collections), was added. The review notes (Section 7) now
record these fixes.

## How I reviewed the output
I reviewed the output that the AI gave me and read through everything to
make sure it made sense. I also went through the list of contradictions and
gaps the AI found in the draft, and decided how each one should be resolved.
In particular, I kept sharing at Could priority instead of accepting the
suggestion to raise it.
