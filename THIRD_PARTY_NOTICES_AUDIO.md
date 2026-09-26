# Audio engine third-party notices

The audio engine is an independent Manju implementation. No upstream source
file is copied into the Manju runtime. The following pinned projects informed
provider contracts and workflow behavior:

| Project | Commit | License | Manju use |
| --- | --- | --- | --- |
| CosyVoice | `074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc` | Apache-2.0 | External HTTP provider contract and reference-audio concepts |
| chatterbox | `5de7a54aa4e5e2baadb0182dde554908b48b85c2` | MIT | Adapter-level dramatic-performance mapping |
| GPT-SoVITS | `48b1a0169a28582a8984402f82cf438d3bfa6aca` | MIT | External `/tts` request shape only |
| VideoLingo | `9bc30202ad87f87e2ecbdfb1cc25d5b9d62849e3` | Apache-2.0 | Duration-estimation and audio-timeline ideas |
| MuseTalk | `0a89dec45a0192b824e3cf4daf96c239440c5ed8` | MIT | Optional separate worker contract |
| OpenVoice | `74a1d147b17a8c3092dd5430504bd83ef6c7eb23` | MIT | Optional provider idea only |
| IndexTTS | `ee40fa7d6c6b8a2c7f06105f9f1e65775b74868c` | Bilibili Model Use License | Optional, license-gated provider only |
| pyVideoTrans | `8ca91f4cdfaab9b3e157a376411777a886f5ad54` | GPL-3.0 | Reference-only; no code copied or adapted |

If a future change copies or substantially adapts an upstream file, retain its
full license/notice and record the upstream path and Manju path here before
shipping.
