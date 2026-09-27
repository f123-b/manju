# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

Current visual direction: recreate the selected desktop storyboard reference as a restrained three-column production workspace. Preserve the left shot rail, central cinematic preview, right inspector, light surfaces, cobalt-blue action color, thin dividers, and high information density without decorative clutter.

Generation behavior: never present a preset image or local mock as a successful image/video result. Without a configured real media Provider, persist a visible Failed task and leave the asset image empty so API integration problems are testable.

Provider behavior: `blankapi.com` is a real user-configured relay in this prototype; only `example.com`-style documentation hosts are treated as placeholders.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.
