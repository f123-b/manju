# Manju Story Engine V1

This module integrates ideas from four permissively licensed 2026 open-source projects without embedding them as parallel applications.

## Upstream inspirations

- **shuohao-skills**: structured outline/script/storyboard schemas, stable IDs, timing constraints, deterministic quality gates.
- **drama-skills**: short-drama hook/payoff/reversal craft, continuity boundaries, production-stage contracts.
- **Script Doctor**: Story Bible, scene purpose, acceptance criteria, plant/payoff thinking.
- **CineCrew**: story/editor/director separation, cinematography fields, structured FilmDSL-like handoff from narrative to production.

The Manju implementation is independent and stores everything in the existing Manju relational domain.

## Canonical chain

Idea / novel / existing script
→ Story Bible
→ Character Bible + Art Bible
→ Episode Plan + Story Beats
→ Scene Purpose + Acceptance Criteria
→ Structured Scene Flow
→ Shot Breakdown
→ Generation Segment
→ Image / Video / Voice production

## Structured scene flow

Dialogue must always carry a stable character ID:

```json
{
  "flow": [
    {"id":"BT001","kind":"action","action":"林泽推开门。"},
    {"id":"BT002","kind":"dialogue","speakerId":"C001","line":"你怎么会在这里？","delivery":"克制、戒备"}
  ]
}
```

This is the authoritative source for DialogueLine extraction. Shot character bindings are visual production data and must not be used to guess speakers.

## Storyboard hierarchy

Scene → Beat → Shot → Generation Segment.

A Segment is the unit sent to a video model and may contain multiple 2–5 second shots, but must not cross a scene and should stay within 15 seconds.

## Deterministic quality gates

The validator checks:
- Story Bible completeness
- episode count and hook/core/ending structure
- Character Bible completeness
- Art Bible anchors
- valid dialogue speaker IDs
- scene acceptance criteria
- shot duration
- cinematography fields
- segment duration

LLM generation is allowed to be creative; the quality gates are deterministic and persisted.
