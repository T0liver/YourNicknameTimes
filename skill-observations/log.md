# Skill Observations Log

Use this log to capture reusable workflow and methodology observations.

### Observation 1: Dispatch artifacts reduce review churn
- **Context:** M0 orchestration kickoff with three parallel task dispatches.
- **Observation:** Creating per-task dispatch contract files before subagent execution improves evidence completeness and reduces ambiguous returns.
- **Potential skill impact:** Keep a reusable "dispatch artifact first" step in manager workflows before any execution wave.
- **Status:** OPEN

### Observation 2: Smoke scripts should emit machine-parseable status
- **Context:** M0-B data smoke implementation and evidence capture.
- **Observation:** Including both human-readable output and JSON in smoke scripts makes handoff evidence and downstream status ingestion easier.
- **Potential skill impact:** Standardize smoke scripts to return explicit exit codes and JSON health summaries.
- **Status:** OPEN

### Observation 3: Smoke tasks need explicit credential-preflight evidence
- **Context:** M0-D delivery smoke implementation in a local environment without OpenRouter/Dropbox secrets.
- **Observation:** A quick preflight check for required secret presence avoids ambiguous “test failed” outcomes and cleanly separates implementation completion from environment readiness.
- **Potential skill impact:** Require `*_set=yes/no` preflight evidence in smoke-task returns before attempting live success-path checks.
- **Status:** OPEN

### Observation 4: Separate implementation acceptance from gate acceptance
- **Context:** M0-B delivered strong implementation evidence but lacked live Baikal success proof.
- **Observation:** Using `in_review` + conditional acceptance keeps momentum while clearly preventing premature milestone gate closure.
- **Potential skill impact:** Apply a standard “implementation accepted / gate pending” status note pattern in backlog evidence fields.
- **Status:** OPEN

### Observation 5: Environment blockers can be burned down in parallel
- **Context:** M0-A (hardware/CUPS), M0-B (live Baikal), and M0-D (secrets) were unblocked independently before final gate close.
- **Observation:** Explicitly separating blocker classes (hardware, credentials, live endpoint) allows parallel unblock work and shortens milestone lead time.
- **Potential skill impact:** Add a standard unblock matrix section to manager cycle outputs for faster closure of smoke milestones.
- **Status:** OPEN

### Observation 6: Prewriting starter prompts reduces dispatch latency
- **Context:** M1 kickoff preparation required immediate launch and one dependency-gated launch.
- **Observation:** Keeping a single starter-prompts file with copy/paste launch text and attachment lists prevents message drift and speeds manager response time.
- **Potential skill impact:** Standardize `<milestone>-starter-prompts.md` as part of each wave dispatch artifact set.
- **Status:** OPEN
