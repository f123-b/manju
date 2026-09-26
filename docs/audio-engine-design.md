# Manju Audio Engine V1 design

## Product boundary

Manju's audio pipeline is a production domain, not a standalone dubbing page:

```text
Scene / Shot -> DialogueLine -> VoiceProfile + VoicePerformance
             -> persistent TTS task -> VoiceTake versions -> Audio QC
             -> dialogue timeline -> mixdown -> optional LipSync task
```

The non-negotiable boundary is `VoiceProfile != VoicePerformance`. A profile
stores a character's stable sound identity, rights provenance and provider
voice handle. Emotion, intensity, speed, pitch, gain, pauses, breath cues and
delivery instructions belong to the individual line performance.

## Source mapping

Pinned source commits were read from the integration pack's `SOURCE_MAP.json`:

- CosyVoice `074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc` (Apache-2.0): external
  HTTP topology, zero-shot reference audio, instruction and streaming concepts.
- Chatterbox `5de7a54aa4e5e2baadb0182dde554908b48b85c2` (MIT): dramatic speech
  mapping to adapter-only exaggeration / CFG values.
- GPT-SoVITS `48b1a0169a28582a8984402f82cf438d3bfa6aca` (MIT): external `/tts`
  request shape; model runtime is not bundled.
- VideoLingo `9bc30202ad87f87e2ecbdfb1cc25d5b9d62849e3` (Apache-2.0): duration
  estimation, segment clips and explicit timeline merge ideas.
- pyVideoTrans `8ca91f4cdfaab9b3e157a376411777a886f5ad54` (GPL-3.0): state
  machine and alignment ideas only; no code is copied.
- MuseTalk `0a89dec45a0192b824e3cf4daf96c239440c5ed8` (MIT): optional separate
  lip-sync worker contract only.
- IndexTTS and OpenVoice remain optional adapters; their weights and license
  obligations are not part of the default runtime.

## Canonical schema

`voice_profiles` are one-to-many from `characters`. The legacy
`characters.voice_profile` JSON is preserved and migrated into a default row.
`dialogue_lines` belong to projects and may point to episode, scene, shot and
character. `voice_performances` are one-to-one child records. `voice_takes`
are immutable alternatives attached to persistent generation tasks. QC rows
are attached to takes, and `audio_clips` provide separate Dialogue / SFX /
Ambience / BGM tracks. A mixdown is a new media asset, never an overwrite of a
take.

The migration keeps the old `shots.dialogue` readable and creates a safe
DialogueLine only when a shot has dialogue and a character binding.

## Provider contract

The domain sends a provider-neutral request with `text`, a structured `voice`
object, a structured `performance` object and `target_duration_ms`. Adapters
translate it to CosyVoice, Chatterbox or GPT-SoVITS syntax. No provider token
or private parameter is stored in domain entities.

CosyVoice is the default configured external provider. If no endpoint is set,
the local mock provider creates deterministic WAV fixtures for development and
tests. The backend never imports the CosyVoice runtime or model weights.

## Duration fit and QC

The duration policy is explicit:

- error <= 5%: pass;
- 5% < error <= 12%: allow controlled stretch or a small speed adjustment;
- error > 12%: recommend regeneration or dialogue shortening; no silent text
  rewrite and no extreme speed-up.

The development provider produces a real WAV fixture. QC uses Python's standard
`wave` reader where available to check file existence/decodability, duration,
silence ratio and peak/clipping. Loudness is recorded as a measurable estimate;
ASR text matching remains optional and is not claimed without an ASR provider.

## Task and impact policy

Audio synthesis, episode batch generation, mixdown and optional lip-sync all
use the existing durable `generation_tasks` worker. A line failure does not
invalidate sibling lines. Voice Profile changes mark its dialogue lines,
takes and dependent mix clips stale; a performance edit marks only the line
chain stale. Locked profiles require an explicit unlock before mutation.

## V1 UI

The existing `素材库` character workspace gains a Voice section, and the
`故事` scene workflow exposes extracted dialogue lines and editable Voice
Performance controls. The `时间线` page shows separate audio tracks and
mixdown controls. There is no disconnected audio application.

## Explicit non-goals

- No bundled GPU TTS runtime or model weights.
- No direct GPL implementation reuse.
- No biometric identification or silent voice cloning.
- LipSync is a separate feature-flagged task contract and does not block P0.
