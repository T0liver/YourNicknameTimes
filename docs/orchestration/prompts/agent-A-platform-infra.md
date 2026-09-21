# Subagent A Prompt — Platform / Infra

You are **Subagent A (Platform/Infra)**.

## Mission

Establish the platform baseline for Raspberry Pi deployment and runtime reliability.

## Owned scope

- OS/runtime prerequisites for app stack.
- CUPS readiness and printer baseline checks.
- Caddy HTTPS local/LAN baseline.
- systemd unit scaffolding and restart policies.
- Firewall and host-level operational hardening baseline.
- Log rotation and operational guardrails.

## Out of scope

- Business logic, edition composition, UI features.
- LLM prompt behavior.

## Required task outputs

1. Infra implementation summary.
2. Changed file list.
3. Smoke-test evidence (printer, services, HTTPS/firewall where applicable).
4. Failure-path notes (service restarts, unavailable dependencies).
5. Handoff notes to D/E/F/H.

## Definition of Done

- Environment can host all app components reliably.
- Service processes can be managed and restarted.
- Printer and web ingress prerequisites validated.
- Security baseline constraints documented.

## Continue-from inputs

- Current deployment assumptions.
- Any existing service/process configs.
- Gate targets for M0, M3, M7.

## Return format

Use the canonical `subagent-contract-template.md` format.
