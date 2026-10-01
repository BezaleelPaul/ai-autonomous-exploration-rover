# Phase 0 â€” Dependency Report

**Date:** 2026-09-25 | **Status:** AWAITING VALIDATION

## 1. Interpreter situation (BLOCKER-adjacent)

| Interpreter | Packages | Usable? |
|---|---|---|
| `python` on PATH â†’ `C:\msys64\ucrt64\bin\python.exe` (3.14.2) | **none** | NO â€” `python -m pytest` fails |
| **`C:\Users\bezal\AppData\Local\Programs\Python\Python312\python.exe` (3.12.10)** | everything below | **YES â€” use this one** |
| Python 3.13 / 3.14 installs | none | NO |

There is **no project `.venv`**. All verification today used the 3.12 install directly.

**Action (Phase 1):** create `.venv` from Python 3.12 and document
`python -m software.main` (or fix R1 so `python software/main.py` works) in README.

## 2. Installed vs required (Python 3.12, measured today)

| Package | requirements.txt | Installed | Note |
|---|---|---|---|
| opencv-python | >=4.8.0 | 5.0.0 | OK (also headless 4.13 present â€” harmless but redundant) |
| numpy | >=1.24.0 | 2.4.6 | OK |
| **pyserial** | >=3.5 | **MISSING** | **P0 for real hardware** â€” mock tests pass because `import serial` is lazy |
| pyyaml | >=6.0 | 6.0.3 | OK |
| pillow | >=10.0.0 | 10.4.0 | OK |
| torch | >=2.0.0 | 2.12.0+cpu | OK, CPU build |
| transformers | >=4.35.0 | 5.12.0 | Loaded OK today (benign `UNEXPECTED` batch-norm keys on DETR) |
| huggingface-hub | >=0.20.0 | 1.19.0 | OK |
| timm | >=0.9.0 | 1.0.29 | OK (not imported by our code â€” candidate to drop) |
| psutil | >=5.9.0 | 7.2.2 | listed **twice** in requirements.txt (lines 15 & 25) |
| flask | >=3.0.0 | 3.1.3 | optional dashboard |
| pytest | >=7.4.0 | 9.1.1 | OK |
| **ultralytics** | commented out | **8.4.155 installed** | `yolo` backend needs it; requirements.txt must uncomment or backend breaks for fresh installs |
| python-docx, reportlab, matplotlib, pandas, networkx, svgwrite, jinja2, openpyxl, qrcode | yes | all present | doc-generation only â€” should be an **optional extras group**, not core |
| **ruff** | not listed | **MISSING** | lint command unavailable; `.ruff_cache` exists from some earlier run |

## 3. requirements.txt issues to fix

1. `psutil` duplicated.
2. `ultralytics` commented out while `detector.py` implements the `yolo` backend and
   weights (`yolo11n/s.pt`, `yolov8*-worldv2.pt`) ship in the repo root.
3. No split between runtime / AI / docs / dev groups.
4. No Python version pin (README says 3.10+; 3.14 is on PATH and has nothing installed).

## 4. Model weights inventory

| File | Size | Backend | License (see LICENSE_REPORT) |
|---|---|---|---|
| `models/detr-resnet-50/` (pytorch_model.bin + config) | ~1.7 GB cache | `hf` | apache-2.0 |
| `yolo11n.pt` | 5.6 MB | `yolo` | AGPL-3.0 (Ultralytics) |
| `yolo11s.pt` | 19 MB | `yolo` | AGPL-3.0 |
| `yolov8s-worldv2.pt` | 26 MB | `yolo` (open-vocab) | REVIEW â€” upstream YOLO-World is CC-BY-NC |
| `yolov8m-worldv2.pt` | 57 MB | configured default in `config.yaml:19` | REVIEW â€” see above |
| `weights/clip/ViT-B-32.pt` | 353 MB | YOLO-World text encoder | REVIEW |

## 5. Measured performance (this laptop, 2026-09-25, CPU)

| Backend | Load | Inference | FPS | Source |
|---|---|---|---|---|
| DETR-ResNet-50 (`hf`) | **58.1 s** | **5420 ms** | ~0.2 | measured today; consistent with `logs/benchmark_detr.json` (5143 ms, 26.7 s load â€” disk-cache dependent) |
| YOLO11s @320 (`yolo`) | **2.6 s** | **1094 ms** | ~0.9 | measured today on a random frame |
| color/mock | n/a | <10 ms | ~50+ | by construction |

**Implication:** DETR is **not usable for tracking** (Phase 5 must benchmark
`yolo11n`, `yolo11s`, and `color` on this machine and pick by measurement â€”
MASTER PROMPT Â§13). Even YOLO11s at ~1 FPS needs frame-skip + the existing
hysteresis/lock logic to steer smoothly.

## 6. Firmware toolchains

| Target | Toolchain | Libraries | Status |
|---|---|---|---|
| Arduino UNO | Arduino IDE / arduino-cli (not installed on PATH â€” verify) | none beyond core (`Servo`/`Wire` would be added later) | build **not yet verified on this machine** |
| ESP32-CAM | arduino-cli + esp32 core, or Arduino IDE with AI-Thinker board | `esp_camera`, `esp_http_server`, `WiFi` (all bundled) | build **not yet verified on this machine** |

## 7. Test baseline (measured today)

```
39 passed in 1.10s   (Python 3.12, python -m pytest tests -q)
```

Mock-only: no hardware-in-the-loop tests exist yet (expected â€” Phase 1/2).

## 8. P0/P1 dependency actions

1. **P0** â€” `pip install pyserial` into the 3.12 env (or new `.venv`) before any real serial test.
2. **P0** â€” decide + document the canonical interpreter/venv; fix README run command (R1).
3. **P1** â€” clean requirements.txt (dedupe psutil, uncomment ultralytics, split extras, add ruff).
4. **P1** â€” verify Arduino/ESP32 build toolchain exists; compile both sketches as Phase 1 entry gate.
