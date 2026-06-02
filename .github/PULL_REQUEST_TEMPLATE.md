# Pull Request Template

## Summary
Describe what the change does and why it is needed.

## Foundational Questions (brief)
- Problem clarity: (one line)
- User / persona:
- How bad is the problem (impact/frequency):
- Why hasn't it been solved already:
- What success looks like:
- What am I NOT solving (boundaries):

## Current State & Metrics
- What works today (short):
- What breaks / user pain (short):
- Primary metric(s) affected (baseline + target):
- How will we measure success after deploy?

## Safety & Risk
- Threats / highest-impact failure modes:
- Rollback plan (how to revert safely):
- Monitoring / alerts added:
- Security/privacy review completed: [ ]

## Experiment / Sprint
- If this is part of an experiment, link the sprint file: (e.g. `sprints/2026-06-02-sprint.md`)
- Decision log / ADR: [DECISION-LOG-ADR.md](DECISION-LOG-ADR.md)

## Checklist (pre-merge)
- [ ] PR description filled
- [ ] Tests added/updated for critical behavior
- [ ] Documentation updated where needed
- [ ] Monitoring & dashboards in place
- [ ] Rollback plan documented
- [ ] Owner / on-call notified for deploy window

---

Helpful links:
- Self-directed framework: [SELF-DIRECTED-EXCELLENCE.md](SELF-DIRECTED-EXCELLENCE.md)
- Two-week template: [TWO-WEEK-IMPROVEMENT.md](TWO-WEEK-IMPROVEMENT.md)
- Decision & ADR template: [DECISION-LOG-ADR.md](DECISION-LOG-ADR.md)
