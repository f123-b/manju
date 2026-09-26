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
