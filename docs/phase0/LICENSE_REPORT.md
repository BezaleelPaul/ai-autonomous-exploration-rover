# Phase 0 — License Report

**Date:** 2026-09-25 | **Status:** AWAITING VALIDATION | **Required output of this phase:** `THIRD_PARTY.md` (created alongside this report)

## 1. This project's own license

**NO LICENSE FILE EXISTS** for the MWE PROJECT repository itself (checked root and
recursive `LICENSE*`/`COPYING*` — none found; no `.git`, so no commit history to
derive provenance from).

- Without a license, the code is "all rights reserved" by default — it cannot be
  lawfully reused, and academic submission/reuse terms are undefined.
- **ACTION (owner decision required):** choose a license (MIT or Apache-2.0 are the
  usual academic defaults) and add `LICENSE` at the repo root. The CLI agent must
  not pick one unilaterally.

## 2. Third-party components in use

| Project | URL / Source | License | Version/Commit | Used components | Modifications |
|---|---|---|---|---|---|
| facebook/detr-resnet-50 (weights + config) | https://huggingface.co/facebook/detr-resnet-50 | **apache-2.0** (confirmed in `models/detr-resnet-50/README.md:2`) | snapshot present in `models/detr-resnet-50/` (exact revision not recorded — **record the HF commit hash**) | `hf` detector backend (weights, config, preprocessor) | none (loaded via transformers API) |
| Ultralytics YOLO (package + weights yolo11n/s, yolov8*world) | https://github.com/ultralytics/ultralytics | **AGPL-3.0** | pip pkg 8.4.155; weights in repo root (exact model version not recorded) | `yolo` detector backend (`detector.py:202-286`), ByteTrack tracking | none |
| YOLO-World (yolov8m/s-worldv2 weights) | via Ultralytics | **AGPL-3.0** package; original YOLO-World (AILab-CVC) is **CC-BY-NC-4.0** → **REVIEW** | weights only in repo root | open-vocabulary detection (`config.yaml:19`) | none |
| OpenAI CLIP ViT-B/32 weights | https://github.com/openai/CLIP | **MIT** (code) — weight-file licensing **REVIEW** | `weights/clip/ViT-B-32.pt` | YOLO-World text encoder | none |
| transformers / torch | https://github.com/huggingface/transformers / pytorch | Apache-2.0 / **BSD-3-Clause** | 5.12.0 / 2.12.0+cpu | model loading + inference | none |
| OpenCV | https://github.com/opencv/opencv | Apache-2.0 | 5.0.0 | camera client, color detector, CLAHE | none |
| pyserial / PyYAML / Flask / psutil / Pillow | PyPI | BSD-3 / MIT / BSD-3 / BSD-3 / MIT-CMU | see DEPENDENCY_REPORT | serial, config, dashboard, benchmark, images | none |
| Espressif ESP32 camera + HTTP server examples | https://github.com/espressif/esp32-camera (+ Arduino `CameraWebServer` example) | **Apache-2.0** | not recorded | `camera_stream.ino` structure (stream handler, pin map) — **high similarity: treat as derivative** | compressed/rewritten to minimal sketch |
| Arduino core / L298N & HC-SR04 community wiring conventions | arduino.cc, ST datasheet | CC-BY-SA docs / datasheet copyright | n/a | pin map, `pulseIn` ranging | our own code |

## 3. Flags

| ID | Issue | Action |
|---|---|---|
| L-1 | **Ultralytics is AGPL-3.0.** Running it (even locally) is fine; *distributing* the project or a network service that includes modified ultralytics code triggers AGPL obligations. For an academic hand-in this is usually acceptable, but it must be disclosed. | Record in `THIRD_PARTY.md`; keep ultralytics as an **optional** backend (it already is: `backend: mock` default). |
| L-2 | YOLO-World weights potentially **CC-BY-NC (non-commercial)** upstream. | REVIEW before any commercial/distribution use; document in THIRD_PARTY.md. |
| L-3 | CLIP weight file license not verified in-repo. | REVIEW; note in THIRD_PARTY.md. |
| L-4 | ESP32 sketch derivative of Espressif Apache-2.0 example — attribution required. | Add copyright/notice header line + entry in THIRD_PARTY.md. |
| L-5 | No project LICENSE (§1). | **Owner decision required.** |
| L-6 | No versions/commits recorded for model weights. | Record SHA/revision when known; HF `.gitattributes`/cache metadata exists for DETR. |

## 4. Verdict

No license is *incompatible* with the MVP. Outstanding: **L-5 (project license =
owner decision)** and **L-2/L-3 (review)**. Create `THIRD_PARTY.md` at root with the
table in §2 — planned as the first Phase 1 commit alongside `docs/PINOUT.md`.
