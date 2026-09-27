# Model and API settings design QA

## Source visual truth

- `C:\Users\lenovo\AppData\Local\Temp\codex-clipboard-4de69c76-2afa-4409-8ed4-49e10ad7b591.png` — service list screen.
- `C:\Users\lenovo\AppData\Local\Temp\codex-clipboard-7c3e002a-b48b-4ba5-8e2d-8aa09fcfd3d0.png` — add model service modal.

## Implementation evidence

- URL: `http://127.0.0.1:8000/`
- Browser: Codex In-app Browser, desktop viewport.
- Implementation capture: inline CUA browser capture, 1017 × 897 px. The browser capture API exposes the image inline rather than a filesystem path.
- States checked: model service list with an existing media Provider; add model service modal in its default LLM state; modal close action.

## Comparison

The implementation preserves the existing product shell and global navigation while matching the selected reference's core settings anatomy: a large Model & API heading, summary pills, rounded provider cards, service status, edit/delete actions, a prominent add-service action, and a scrollable add-service modal with Base URL, API key, connection test, model discovery, routing, and save actions.

### Required fidelity surfaces

- Fonts and typography: Inter plus Noto Sans SC matches the existing product shell; compact labels, service names, and modal hierarchy are readable at the captured desktop size.
- Spacing and layout rhythm: provider cards use the reference's generous padding, rounded corners, thin dividers, and separated modal footer; the project settings block is intentionally secondary.
- Colors and visual tokens: cobalt blue actions, pale blue/violet service icons, green connected states, white cards, and restrained gray-blue copy match the reference direction.
- Image quality and asset fidelity: the reference contains UI icons only; the implementation uses the existing Phosphor icon system rather than raster or CSS approximations.
- Copy and content: service name, Base URL, API Key, model routing, model discovery, connection testing, and secure local storage copy are present in Chinese and map to real actions.

## Findings

- No actionable P0/P1/P2 visual findings remain after the final pass.
- P3 / intentional deviation: the existing product's global left navigation remains visible instead of adding a second settings-only navigation rail from the reference. This keeps navigation consistent across the app and avoids duplicate navigation.

## Interaction checks

- Opened 设置 and verified the new Model & API screen.
- Opened 添加模型服务 and verified the LLM / Agent and 图片 / 视频 type choices, routing fields, disabled empty-state actions, and save footer.
- Closed the modal and returned to the provider list.
- Existing API tests, model discovery, and provider persistence tests all pass.

## Comparison history

1. Initial implementation: provider cards and modal were visually aligned; the current-service summary treated only one provider kind as current.
2. Fix: current status now reports LLM and generation services independently, matching the backend's separate routing semantics; the non-persistent “set current” affordance was removed.
3. Final inline browser capture: no actionable P0/P1/P2 findings.

final result: passed
