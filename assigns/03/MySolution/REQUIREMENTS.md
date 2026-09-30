# Requirements Specification: LAMBDA Web Testing Environment

## 1. Purpose, Stakeholders and Scope

### 1.1 Purpose

This document specifies version 1 of the LAMBDA Web Testing Environment, a
tool that runs locally in a web browser and lets users write LAMBDA programs,
send them to the LAMBDA compiler, inspect the results, and keep programs as
repeatable tests. It is based on the instructor's stakeholder brief. Where
the brief leaves a question open, the gap is recorded in Section 2 as an
assumption or an unresolved issue.

### 1.2 Stakeholders

| Stakeholder | Role | Main goals |
|---|---|---|
| Students writing programs | Primary user | Try examples, write and save programs, understand results and errors. |
| Students changing the compiler | Primary user | Keep a collection of tests and rerun it to see whether a compiler change broke anything. |
| Instructor | Primary user and requirements owner | Show and modify examples in lectures with little interface overhead; hand out example collections. |
| Compiler developers | External dependency | Provide and maintain the compiler interface the environment uses (A1). |

### 1.3 Scope

**Environment vs. compiler.** The environment handles editing, sending
programs to the compiler, displaying what comes back, managing tests, and
saving work. The compiler handles parsing, checking, and running programs.
The environment never interprets LAMBDA itself; everything it reports about
a program comes through the compiler interface. Building the compiler is a
separate project.

**In scope for version 1:**
- Editing programs, built-in examples, and importing/exporting program files
- Checking and running programs, with results, errors, and optional compiler details
- Stopping runs and an automatic time limit
- Named test collections that can be run, summarized, and saved
- A mock compiler for use before the real one is ready
- Running locally on one computer in a supported browser

**Out of scope for version 1:**
- The compiler itself
- A public website, hosting, or user accounts
- Several people editing the same program together
- Full development environment features (debugger, autocomplete, refactoring)

**Deferred to a later version:**
- Sharing collections by link (file export is used instead, if delivered; A6)
- Tests that match specific error messages or locations (A5)
- Displaying output printed while a program runs (A2)

## 2. Clarification Questions and Assumptions

No stakeholder answers to these questions were available when this document
was written. Every entry below is therefore either an **Assumption** (a
proposal made by the author so that work can proceed, not a decision by the
instructor) or marked **Unresolved**. Each assumption is referenced by its
identifier (A1, A2, …) wherever a requirement depends on it, so that it can be
revisited if the instructor answers differently.

| ID | Question for the instructor | Why the answer matters | Status |
|---|---|---|---|
| Q1 | What will the compiler interface look like? In particular: what input does it accept (source text in a notation still being designed, or ASTs built in Python), how is it invoked (command, local service, library call), and what does it return (value, error messages, error locations, AST, generated code)? | Almost every requirement about running programs, showing errors at a source location, and displaying compiler details depends on what the compiler can actually provide. A wrong guess here is the most expensive mistake in the project. | **Unresolved**, see A1 |
| Q2 | What kinds of results can a LAMBDA program produce (integers and Booleans only, or also strings, pairs, functions)? Can a program print output while it runs? | Determines how results are displayed and how a test decides whether an actual result matches the expected one. | **Assumption** A2 |
| Q3 | Where should saved work live? Is it enough that work survives a page refresh and browser restart on the same computer, or must it also survive clearing browser data or moving to another computer? | "Come back to their work in another session" can mean very different storage requirements. Browser-only storage is simple but fragile; files are durable but need user action. | **Assumption** A3 |
| Q4 | When a program runs for a long time, should the environment stop it automatically after a time limit, and if so, what limit? | The brief requires a way to stop a program, but test collections run unattended. Without an automatic limit, one non-terminating test would block the whole collection. | **Assumption** A4 |
| Q5 | What can a test expect? Only "produces value V" and "is rejected by the compiler", or also "fails while running", or a specific error message or location? | Defines what "passed" means for a test. Matching exact error text would make tests break whenever the compiler's wording changes. | **Assumption** A5 |
| Q6 | What does "sharing a collection with the class" mean: handing out a file, or a link on a hosted site? | A file can be supported by the same export/import feature used for saving. A hosted link needs a server, which the brief places out of scope for version 1. | **Assumption** A6 |
| Q7 | Which browsers and operating systems must be supported, and what may we assume a student already has installed (for example Python)? | Needed to make "a browser students normally use" and "straightforward setup" testable, and to know what the setup instructions may rely on. | **Assumption** A7 |
| Q8 | Which built-in examples should be included, and who maintains them? Are there display needs for lectures, such as readable text size on a projector? | The examples are central to lecture use and first-time users. Lecture display needs affect usability requirements. | **Assumption** A8 |

### Assumptions

- **A1 (compiler interface).** The environment talks to the compiler only
  through a single documented interface, to be agreed with the compiler
  developers. The environment sends the program text and a mode ("check
  only" or "run"). It receives:
  - an outcome category (success, compile error, runtime error)
  - a result value, when there is one
  - messages, each with an optional line and column
  - optional extra information, such as an AST or generated code

  Until the real compiler exists, a mock implementation of the same interface
  returns sample responses. The exact data format is **unresolved**.
- **A2 (results).** A result is shown as the text the compiler produces for
  it. Tests compare results as text, which works for integers and Booleans
  and for any other value the compiler can print. Program output while
  running is **unresolved** and out of scope until the compiler supports it.
- **A3 (persistence).** Work is saved automatically in the browser, so it
  survives a refresh and a browser restart on the same computer. Individual
  programs can also be saved to and opened from files (FR3, FR4), which lets
  a student move a program to another computer. Moving a whole test
  collection to another computer depends on collection export (FR18), which
  is a Could-priority feature; if it is not delivered, collections stay on
  the computer where they were created in version 1.
- **A4 (time limit).** The user can stop any check or run at any time. In
  addition, we propose a default automatic time limit of 10 seconds per
  check or run, which the user can change. A test that reaches the limit is
  recorded as "timed out" and the rest of the collection continues. The
  10-second value is our proposal, not the instructor's.
- **A5 (test expectations).** A test expects exactly one of three outcomes:
  - a specific result value (compared as text, see A2)
  - rejection by the compiler (any compile error)
  - a failure while running (any runtime error)

  Matching specific error messages or locations is deferred to a later
  version.
- **A6 (sharing).** Sharing a collection means exporting it to a file that
  the instructor can distribute and students can import (FR18). Because the
  brief says the instructor "could live without" sharing in version 1, this
  is Could priority. Hosted sharing links are out of scope.
- **A7 (platform and setup).** Version 1 must work in the current versions
  of Chrome and Firefox on Windows, macOS and Linux. Setup instructions may
  assume Python 3 is installed, since the course tools already use Python.
  We propose that a student who has not used the environment before can
  complete setup from the written instructions in 15 minutes or less.
- **A8 (examples and lectures).** The instructor supplies the initial example
  set (for example factorial) as a file that ships with the environment. We
  propose that switching to any built-in example takes no more than two
  actions, and that the text size can be increased for projection.
- **A9 (several collections).** A user may keep more than one named test
  collection, for example the instructor's examples alongside their own
  tests. The brief speaks of "a collection", but importing a shared
  collection (A6) only makes sense if it does not replace the user's own.

## 3. Requirements

### 3.1 Priorities

- **Must:** version 1 is not acceptable without it.
- **Should:** expected in version 1, but can move to a later version if time runs out.
- **Could:** included only if time allows.

These priorities follow the brief's statement that reliable editing,
understandable results, and repeatable tests matter more than extra features.

### 3.2 Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR1 | The environment shall provide a list of built-in examples (A8). A user shall be able to load any example into the editor in no more than two actions. | Must |
| FR2 | Editing a loaded example shall not change the original. The user shall be able to restore the original text of the example. | Must |
| FR3 | The user shall be able to open a program from a text file on their computer into the editor. | Must |
| FR4 | The user shall be able to save the program in the editor to a text file. | Should |
| FR5 | The environment shall automatically save the editor contents and all test collections in the browser, so that they are restored after a page refresh or browser restart on the same computer (A3). | Must |
| FR6 | The user shall be able to request either "check only" or "run" for the program in the editor (A1). | Must |
| FR7 | When a request finishes, the environment shall show its outcome category and, for a successful run, the result value as text (A2). | Must |
| FR8 | Compile errors, runtime errors, and environment errors (compiler unreachable or invalid response) shall each be shown with a different text label. An environment error message shall state that the problem is not in the user's program. | Must |
| FR9 | When a message includes a line and column, the environment shall show that location and let the user move the editor cursor to it in one action. | Must |
| FR10 | When the compiler returns extra information (such as an AST or generated code), the environment shall make it available in a view that is hidden by default and opened on request. | Should |
| FR11 | The user shall be able to stop any check or run in progress. The stopped request shall be reported as "stopped by user". | Must |
| FR12 | A check or run that exceeds the time limit shall be stopped automatically and reported as "timed out". The limit defaults to 10 seconds and can be changed by the user (A4). | Must |
| FR13 | Each displayed result shall identify the version of the program that produced it. If the program has been edited since the request was sent, the result shall be marked as out of date. | Must |
| FR14 | When the mock compiler is in use, every result shall be labeled as a sample response, and the environment shall show at all times whether the mock or the real compiler is connected. | Must |
| FR15 | The user shall be able to create, rename, and delete named test collections (A9), and to create, edit, rename, and delete named tests within a collection. Each test contains a program and exactly one expected outcome (A5). | Must |
| FR16 | The user shall be able to run every test in a collection with one action. Tests shall run independently, so a test that fails, errors, or times out shall not stop the remaining tests from running. | Must |
| FR17 | After a collection run, the environment shall show the number of tests that passed, failed, timed out, and could not run because of an environment error. For each test that did not pass, it shall show the expected outcome, the actual outcome, and any messages. | Must |
| FR18 | The user shall be able to export a test collection to a file and import a collection from a file as an additional collection (A6, A9). | Could |
| FR19 | The user shall be able to increase the text size of the editor and results to at least 200% of the default (A8). | Should |

### 3.3 Quality Requirements

| ID | Requirement | How it is assessed | Priority |
|---|---|---|---|
| QR1 | Every Must-priority task in 3.2 can be done using only the keyboard. | Walk through each Must requirement without a mouse. | Must |
| QR2 | Every status (passed, failed, timed out, compile error, runtime error, environment error, out of date) is shown with text or a symbol, not only color. | Review each status in grayscale. | Must |
| QR3 | While a check, run, or collection run is in progress, editing and the stop control respond to input within 0.5 seconds. *(Proposed target.)* | Start a long-running program, then type and press stop, and time the response. | Must |
| QR4 | No compiler failure, lost connection, or timeout causes loss of the editor contents or test collections. | Stop the compiler during a run and confirm that all work is still present. | Must |
| QR5 | A person who has not used the environment before can install and start it from the written instructions in 15 minutes or less (A7). | Give the instructions to someone new and time them. | Should |

## 4. External Interfaces and Dependencies

| ID | Interface | Description |
|---|---|---|
| IF1 | Compiler interface | The environment communicates with the compiler only through the interface described in A1: it sends program text and a mode, and receives an outcome category, an optional result value, messages with optional line and column, and optional extra information. The data format is unresolved (Q1). Because all compiler access goes through this one interface, the real compiler can replace the mock without changes to the rest of the environment. |
| IF2 | Mock compiler | Implements the same interface as IF1 and returns sample responses. It shall be able to produce each outcome category (success, compile error with a location, runtime error, extra information) and a response that never finishes, so that time limits can be demonstrated. |
| IF3 | Browser | Current versions of Chrome and Firefox on Windows, macOS and Linux (A7). Browser storage is used for automatic saving (FR5). |
| IF4 | Local files | Programs are imported and exported as plain text files (FR3, FR4). If FR18 is delivered, test collections use a documented file format. |
| IF5 | Setup | Setup instructions may assume Python 3 is installed (A7). No internet connection or server outside the user's computer is required. |

**Dependencies and risks.** The compiler is not finished and the source
notation is still being discussed (Q1). The environment therefore makes no
assumptions about LAMBDA syntax; for example, syntax highlighting is not
required in version 1. If the real interface differs from A1, requirements
FR6–FR10 and FR14 must be reviewed.

## 5. Acceptance Criteria

Checks marked *(failure)* cover error or exceptional behavior.

| ID | Req | Starting condition | Action | Expected result |
|---|---|---|---|---|
| AC1 | FR1, FR2 | Environment open with the real compiler connected; factorial is a built-in example that computes the factorial of 5. | Load factorial, change its input from 5 to 6, run it, then restore the original. | Factorial loads in two actions or fewer. The result shown is 720. After restoring, the editor shows the original text, and loading factorial again also shows the original. |
| AC2 | FR5 | Editor contains an edited program; one collection with three tests exists. | Refresh the page. Then close the browser and reopen the environment. | After each step, the edited program and all three tests are present and unchanged. |
| AC3 | FR8, FR9 *(failure)* | Mock compiler configured to return a compile error at line 3, column 5. | Run the program, then activate the error location. | Result is labeled "Compile error" with the message and location shown. The editor cursor moves to line 3, column 5. A runtime error response is shown with a different label. |
| AC4 | FR8, QR4 *(failure)* | Compiler not running; editor contains a program that has not been exported to a file. | Run the program. Then start the compiler and run again. | First run shows an environment error stating that the problem is not in the program. Program text is unchanged. The second run completes without the user re-entering anything. |
| AC5 | FR12, FR16, FR17 *(failure)* | Time limit is 10 seconds. Collection has three tests: T1 expects 120 and returns 120; T2 is a recursive program that never finishes; T3 expects 120 but returns 24. | Run the collection. | T2 is stopped after about 10 seconds and reported as timed out. T1 and T3 still run. Summary shows 1 passed, 1 failed, 1 timed out, 0 environment errors. Details for T3 show expected 120 and actual 24. |
| AC6 | FR11, QR1, QR3 | A program that never finishes is running. | Using only the keyboard, type in the editor, then activate the stop control. | Typed text appears within 0.5 seconds. The stop control visibly responds within 0.5 seconds, and the run is then reported as "stopped by user". |
| AC7 | FR13 | Mock compiler set to delay responses by 5 seconds. | Run the program, then edit it before the result arrives. | When the result arrives, it is marked as out of date and identifies that it came from the earlier version. |
| AC8 | FR14 | Mock compiler connected. | Run any program. | The result is labeled as a sample response, and the screen shows that the mock compiler is connected. |

## 6. Traceability

Brief sections are cited by their headings in the stakeholder brief. No
stakeholder answers were received, so the only other sources are the
assumptions in Section 2.

| Req | Source in the brief | Assumption |
|---|---|---|
| FR1 | Trying a program: "a few examples to start from"; select factorial in a lecture | A8 |
| FR2 | Trying a program: "modify an example without losing access to the original" | |
| FR3 | Trying a program: programs "saved in files", "should not have to retype them" | |
| FR4 | Trying a program: "keep a program they have written and return to it later" | A3 |
| FR5 | Keeping examples as tests: refreshing must not lose examples; return "in another session" | A3 |
| FR6 | Trying a program: "only want to check whether a program compiles" vs. "run it" | A1 |
| FR7 | Understanding what happened: "The result should be easy to understand" | A2 |
| FR8 | Understanding what happened: compile errors and runtime failures "should not look like the same thing"; unreachable compiler must not look like a program error | |
| FR9 | Understanding what happened: "help the student find that place in the source" | A1 |
| FR10 | Trying a program: inspect AST or generated code, without detail getting "in the way" | A1 |
| FR11 | Understanding what happened: "a way to stop it and move on" | |
| FR12 | Understanding what happened: programs that "never finish"; Keeping examples as tests: "One troublesome test" | A4 |
| FR13 | Understanding what happened: "know which version produced the result" | |
| FR14 | The compiler is still evolving: sample responses acceptable "as long as nobody mistakes them" | A1 |
| FR15 | Keeping examples as tests: "collection of named tests"; tests expecting an answer or a rejection | A5, A9 |
| FR16 | Keeping examples as tests: "run the collection again"; one test must not make the rest useless | A4 |
| FR17 | Keeping examples as tests: "quick summary" with "enough detail to investigate" | A5 |
| FR18 | Keeping examples as tests: sharing is useful, but "could live without that" in version 1 | A6, A9 |
| FR19 | Introduction and Keeping the project manageable: use in lectures | A8 |
| QR1 | Keeping the project manageable: "main tasks with a keyboard" | |
| QR2 | Keeping the project manageable: messages must not depend "only on colors" | |
| QR3 | Keeping the project manageable: "respond promptly"; Understanding what happened: page "should remain usable" | 0.5 s is a proposal |
| QR4 | Understanding what happened: "keep their work and try again"; Keeping examples as tests: refresh must not lose work | A3 |
| QR5 | Keeping the project manageable: setup "straightforward enough that another person can follow the instructions" | A7 |
| IF1 | The compiler is still evolving: coordinate on the interface; connect the real compiler "without starting the interface over" | A1 |
| IF2 | The compiler is still evolving: work proceeds "before the compiler is ready" | A1 |
| IF3 | Keeping the project manageable: "a browser students normally use" | A3, A7 |
| IF4 | Trying a program: files; Keeping examples as tests: sharing | A3, A6 |
| IF5 | Keeping the project manageable: "running locally" is enough | A7 |

## 7. Review Notes

| # | Issue found in the draft | How it was addressed |
|---|---|---|
| 1 | **Unverifiable wording.** The brief asks for the environment to "respond promptly", which cannot be tested as written. | QR3 sets a 0.5 second target for editing and the stop control during a run. It is marked as a proposal, and AC6 checks it. |
| 2 | **Misleading test results.** If a test that could not reach the compiler were counted as failed, an outage would look like a compiler bug. | FR17 reports environment errors as a separate count, consistent with FR8. |
| 3 | **Contradiction between assumptions and priorities.** A3 and A6 relied on exporting test collections, but FR18 (collection export) is only Could priority. | A3 and A6 now state that moving or sharing whole collections depends on FR18, and what happens if it is not delivered. FR18 stays Could, since the brief says sharing can wait. |
| 4 | **Check that could not be carried out.** AC1 expected the result 720, but before the real compiler exists only the mock responds, and it returns sample answers rather than computing factorial. | AC1's starting condition now requires the real compiler. Checks that can run earlier (AC3, AC7, AC8) use the mock explicitly. |
| 5 | **Acceptance check stronger than its requirement.** AC6 required the run to stop within 0.5 seconds, but QR3 only requires the stop control to respond in that time; how fast a run actually ends depends on the compiler. | AC6 now checks that the stop control responds within 0.5 seconds and that the run is then reported as "stopped by user". |
| 6 | **Missing behavior.** The time limit applied only to runs, although a check can also fail to finish. FR15 also did not say whether a user could have more than one collection, even though importing one implies it. | FR12 and A4 now cover checks and runs. A9 and FR15 allow several named collections. |
| 7 | **Ambiguous wording.** "Know which version produced the result" did not say what the user should see. | FR13 requires each result to identify its program version and to be marked out of date after an edit. AC7 checks this. |

**Remaining open issues.**

- **Compiler data format.** The exact data format of the compiler interface is still open (Q1, A1).
- **Program output.** Output printed while a program runs is out of scope until the compiler supports it (A2).
- **Stopping a collection run.** FR11 covers stopping a single check or run. Whether stopping during a collection run should stop only the current test or the whole collection is **unresolved** and should be confirmed with the instructor.
