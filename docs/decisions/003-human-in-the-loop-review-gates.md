# 003 - Implement Human-in-the-Loop Review Gates

## Status
Accepted

## Context
The system generates book content using AI, which requires human oversight to ensure quality, coherence, and alignment with user intent. Key requirements:
- Prevent automatic progression from outline to chapters without review
- Allow users to provide feedback and request revisions
- Enable final approval before book compilation and export
- Support different review workflows (strict review vs. auto-approve)
- Track review status and history
- Provide clear visual indicators of content readiness
- Support collaborative review processes

Alternative approaches considered:
- Fully automatic generation (no human intervention)
- Post-generation review only (review after full book created)
- Advisory AI suggestions without gating
- External review system (email-based or separate tool)
- Batch review (review multiple chapters at once)

## Decision
Implemented human-in-the-loop review gates at key transition points:
1. **Outline Review Gate**: Outline must be approved (`approved` or `no_notes_needed`) before chapter generation can begin
2. **Chapter Review Gate**: Each chapter must be approved before the next chapter can be generated
3. **Final Review Gate**: Final review must be cleared (`no_notes_needed`) before book compilation and export is allowed

Implementation details:
- Status tracking using `StageStatus` enum: `pending_review`, `pending_notes`, `approved`, `no_notes_needed`, `outline_review`
- Phase tracking using `BookPhase` enum: `outline`, `chapters`, `completed`
- API endpoints for updating status with human notes:
  - `PATCH /books/{id}/outline` for outline review
  - `PATCH /chapters/{id}` for chapter review
  - `PATCH /books/{id}/final-review` for final review
- Automatic webhook triggers when content is approved
- Configuration option for auto-approving outlines (`auto_approve_outline` flag)
- Global setting for requiring human review (`require_human_review`)

## Consequences
### Positive
- Ensures quality control and user satisfaction
- Prevents wasteful AI generation on unwanted content
- Provides clear checkpoint for user feedback and iteration
- Supports both strict review workflows and flexible auto-approve options
- Creates audit trail of review decisions and feedback
- Enables collaborative workflows with multiple reviewers
- Aligns with responsible AI development practices
- Reduces risk of generating inappropriate or off-content material

### Negative
- Increases time to complete book generation (requires human intervention)
- Adds complexity to the API and state management
- Requires users to understand and engage with the review process
- Potential bottleneck if reviewers are slow to respond
- More complex UI/UX needed to convey review states

### Neutral
- Review gates can be bypassed via configuration for trusted workflows
- Status model is flexible enough to accommodate different review processes
- Implementation follows common patterns in content management systems

## Related Documents
- [PRD.md](../PRD.md) - Product requirements detailing human-in-the-loop workflow
- Source code in `app/api/routes.py` (review gate functions)
- Source code in `app/api/generation.py` (generation endpoints with gating)
- Source code in `app/services/db_service.py` (status update functions)
- Source code in `app/models.py` (StageStatus and BookPhase enums)
- API documentation showing review endpoints