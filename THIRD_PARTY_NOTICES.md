# Third-party notices

Short Drama OS contains a Manju-native Character Asset Engine informed by the
following pinned open-source projects supplied in
`manju_character_engine_integration_pack`:

| Project | Commit | License | Use in Manju |
| --- | --- | --- | --- |
| LocalMiniDrama | `adaecf71a38277126fbe1e5e0d79664300f855c1` | MIT | Character extraction, anchor, reference-sheet and prompt-injection concepts |
| drama-skills | `b71cb3ca9343eaf6c0375725ccc9261a4e79021e` | MIT | Stable identity / mutable look separation, reference lifecycle and continuity-lock concepts |
| lumenx | `f2a02e23171447c939e7d8e1386b24d17049bbf1` | MIT | Canonical reference-sheet and structured provider-reference concepts |
| Jellyfish | `a9678194ddf2d9be3ccbe78d4287d87d5089e123` | Apache-2.0 | Character/look/reference relational modeling concepts |

No source code from these projects is copied into the Manju repository. The
implementation is an independent, Manju-native design that keeps the original
projects' license obligations separate from Manju source. If a future change
copies or adapts upstream code, retain the applicable full license and notice
files in the copied module and update this document.


## Story Engine inspirations

The Manju-native Story Engine is independently implemented after studying these pinned open-source projects:

| Project | Commit | License | Ideas studied |
| --- | --- | --- | --- |
| shuohao-skills | `ef4ac0c313c7eeb1f918db5f0f0eb319745900bc` | Apache-2.0 | Structured outline/script/storyboard schemas, timing rules, deterministic validation |
| drama-skills | `0afa4ea253cf4d1aa2d134863b15a592547cfb54` | MIT | Short-drama development craft, continuity contracts, hook/payoff/reversal workflow |
| script-doctor | `e4a7460a7fc4cd6e1d106fcbbb248273daec4c49` | MIT | Story Bible, beat planning, scene acceptance criteria |
| CineCrew | `9a00efa7db65ba028c1523907f6cee844776123a` | Apache-2.0 | Crew separation, cinematography fields, narrative-to-production structured handoff |

No upstream source file is copied verbatim. Manju uses its own relational schema, services and API contracts.
