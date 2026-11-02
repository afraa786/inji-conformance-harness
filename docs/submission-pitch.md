# Inji Conformance Harness — pitch presentation content

This is presentation source content, not a rendered PPTX or PDF. An existing
external deck was not located or changed. Current acceptance remains incomplete.

## 1. Problem

Service health does not prove protocol interoperability. Certify and Verify need
repeatable tests, component-specific handoffs and traceable failure evidence.

## 2. Solution

A Python REST driver orchestrates the OpenID Foundation Conformance Suite. Java
TestNG adapters and an Extent listener connect protocol outcomes to reviewable
reports. Docker Compose provides the local runtime and trusted gateway.

## 3. Implemented prototype

- Certify and Verify execution modes, plus combined reporting.
- Real backend handoffs, JSON/Markdown results and raw evidence exports.
- Regression-tested result handling and configurable execution-time gates.
- Reviewed native metadata and scoped SD-JWT status-list fixes.

See `architecture.md` for the actual component diagram.

## 4. Evidence

The 2026-10-31 combined run recorded 5 PASSED, 7 FAILED, 12 INTERRUPTED,
1 WARNING and 1 SKIPPED; exit 1. These are retained historical results.
Use `artifacts/demo/final-submission-readiness.md` for current regression counts
and infrastructure checks. Unit passes are not protocol conformance passes.

## 5. Remaining integration

No external AS or registered clients are provisioned. Certify needs compatible
authorization/grant coordination and resource-side DPoP proof validation. Verify
needs genuine browser-owned transaction evidence linked to suite results.
Operational performance budgets require approved values.

## 6. Value and next milestone

The prototype makes protocol failures reproducible and visible. Complete the
missing integrations, rerun all workflows, and assess acceptance from actual
protocol results. Do not present the current project as acceptance-ready.
