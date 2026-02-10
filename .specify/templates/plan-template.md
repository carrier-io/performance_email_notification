# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]  
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]  
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]  
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]  
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [single/web/mobile - determines source structure]  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify compliance with `.specify/memory/constitution.md` (v2.0.0):

- [ ] **I. Results Post-Processing Accuracy**: Changes to threshold matching, baseline comparison, deviation calculations, or quality gate logic?
  - If YES: Document logic BEFORE implementation in relevant .md file (THRESHOLD_MATCHING_LOGIC.md, DEVIATION_LOGIC.md, QUALITY_GATE_REFERENCE.md)
  - Plan tests covering edge cases (missing data, zero values, boundaries, disabled SLA)
  - Verify both API and UI flows maintain parity

- [ ] **II. Code Quality & Maintainability**: Will new code introduce complexity?
  - Methods under 100 lines? Cyclomatic complexity under 10?
  - Magic numbers extracted to constants? Color constants centralized?
  - Shared API/UI logic extracted to utilities (not duplicated)?

- [ ] **III. Chart Generation & Visual Consistency**: Adding or modifying charts?
  - If YES: Use centralized color palette (SUCCESS_GREEN, WARNING_YELLOW, ERROR_RED)
  - Verify chart data matches table data exactly
  - Test rendering at appropriate DPI (300 bar charts, 72 line charts)

- [ ] **IV. Email Template Development**: Modifying templates?
  - If YES: Template-context synchronization verified?
  - Graceful degradation for missing optional data?
  - Both backend_email_template.html and ui_email_template.html updated if feature applies to both?
  - Test rendering in Gmail, Outlook, Slack

- [ ] **V. API vs UI Notification Parity**: Feature affects one notification type?
  - If YES: Evaluate applicability to other type
  - Document divergence in AGENTS.md if types differ intentionally
  - Test both notification flows after shared code changes

- [ ] **VI. Results Presentation Clarity**: Adding warnings or status indicators?
  - If YES: Use color + emoji + text (not color alone)
  - Follow QUALITY_GATE_REFERENCE.md pattern (condition, message, action, data display)
  - Use human-readable metric labels

- [ ] **VII. Backward Compatibility for Event Contracts**: Changing Lambda event parameters?
  - If YES: New parameters are optional with defaults?
  - No removed/renamed required parameters?
  - No type changes (string → dict is BREAKING)?
  - Update README.md and AGENTS.md with parameter changes

- [ ] **VIII. Error Handling & Debugging Support**: Code can fail (API calls, calculations, SMTP)?
  - If YES: Errors include actionable context (URL, status, input values)?
  - Structured logging format used?
  - Debug sections added to templates for production troubleshooting?

*Flag any violations and justify them in the Complexity Tracking section.*

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
