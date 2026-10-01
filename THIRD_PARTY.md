# THIRD_PARTY.md

Third-party components used by this project. Created in Phase 0 (2026-09-25).
Full license analysis: `docs/phase0/LICENSE_REPORT.md`.

| Project | Repository / URL | License | Version / Commit | Used components | Modifications |
|---|---|---|---|---|---|
| facebook/detr-resnet-50 | https://huggingface.co/facebook/detr-resnet-50 | Apache-2.0 | local snapshot in `models/detr-resnet-50/` (exact HF revision: TO RECORD) | `hf` detector backend weights/config/preprocessor | None (loaded via `transformers`) |
| Ultralytics YOLO | https://github.com/ultralytics/ultralytics | AGPL-3.0 | pip 8.4.155; weights in repo root: `yolo11n.pt` 5.61 MB, `yolo11s.pt` 19.31 MB (shipped), `yolo26n.pt` 5.54 MB, `yolo26s.pt` 20.42 MB (pulled for `reports/MODEL_BENCHMARK.md`), reserve `yolo12n.pt`, `yolov10n.pt`, `yolov8s/m-worldv2.pt` (exact upstream release tags: TO RECORD; all `*.pt` are gitignored) | `yolo` detector backend + ByteTrack (`software/ai/detector.py`) | None |
| RT-DETRv2 (PekingU) | https://huggingface.co/PekingU/rtdetr_v2_r18vd · upstream https://github.com/lyuwenyu/RT-DETR · arXiv:2407.17140 | upstream Apache-2.0; HF card license **TO VERIFY** | pulled into the Hugging Face hub cache on 2026-09-26 while benchmarking — not committed to the repo | benchmark candidate only (`ai.backend: hf`), **rejected** — 3427 ms p50, 6.85 s refresh (see `reports/MODEL_BENCHMARK.md`) | None |
| COCO128 labelled benchmark (COCO subset) | https://github.com/ultralytics/yolov5/releases/download/v1.0/coco128.zip (derived from https://cocodataset.org) | CC BY 4.0 (COCO images/annotations) | fetched on demand by `scripts/eval_detection.py` into `datasets/coco128/` (128 images + YOLO-format labels) | accuracy ground truth for multi-object detection eval | None (data, not code) |
| YOLO-World weights | https://github.com/AILab-CVC/YOLO-World (distributed via Ultralytics) | CC-BY-NC-4.0 upstream / AGPL-3.0 via Ultralytics — **REVIEW** | weights only in repo root | open-vocabulary detection (`config.yaml` `ai.yolo_model`) | None |
| OpenAI CLIP | https://github.com/openai/CLIP | MIT (code); weight-file terms **REVIEW** | `weights/clip/ViT-B-32.pt` | YOLO-World text encoder | None |
| PyTorch | https://github.com/pytorch/pytorch | BSD-3-Clause | 2.12.0+cpu | inference runtime | None |
| ONNX | https://github.com/onnx/onnx | Apache-2.0 | 1.23.0 (installed 2026-09-26) | **export-only tooling** — `YOLO.export(format='onnx')` produced `yolo11s.onnx` for the runtime-axis benchmark; never imported by rover code, therefore not in `requirements.txt` | None |
| ONNX Runtime | https://github.com/microsoft/onnxruntime | MIT | 1.24.4 | inference engine behind `ai.yolo_model: yolo11s.onnx` — the measured-ONNX arm of `reports/MODEL_BENCHMARK.md` §6 | None |
| OpenVINO | https://github.com/openvinotoolkit/openvino | Apache-2.0 | 2026.4.0 (installed 2026-09-26) | **export + evaluation tooling** — produced and ran the measured OpenVINO arm (rejected: slower than PyTorch on this host); never imported by rover code, therefore not in `requirements.txt` | None |
| Hugging Face transformers | https://github.com/huggingface/transformers | Apache-2.0 | 5.12.0 | model loading/post-processing | None |
| OpenCV | https://github.com/opencv/opencv | Apache-2.0 | 5.0.0 | stream client, color detector, CLAHE | None |
| pyserial | https://github.com/pyserial/pyserial | BSD-3-Clause | >=3.5 (install pending) | Arduino serial link | None |
| PyYAML | https://github.com/yaml/pyyaml | MIT | 6.0.3 | configuration | None |
| Flask | https://github.com/pallets/flask | BSD-3-Clause | 3.1.3 | optional dashboard | None |
| Espressif esp32-camera / CameraWebServer example | https://github.com/espressif/esp32-camera , https://github.com/espressif/arduino-esp32 | Apache-2.0 | not recorded | MJPEG stream handler + OV2640 pin map in `esp32/camera_stream/camera_stream.ino` | Compressed/rewritten to a minimal sketch — attribution header to be added in Phase 3 |
| Arduino core & community wiring references | https://github.com/arduino/ArduinoCore-avr | LGPL-2.1 (core) | toolchain: TO VERIFY | `pulseIn`, `analogWrite` usage | None |

**Flags:** Ultralytics = AGPL-3.0 (disclose on distribution); YOLO-World/CLIP weight
terms = REVIEW; COCO/COCO128 = CC BY 4.0 (attribution required — table row above
is that attribution); project's own license = **UNDECIDED** (no LICENSE file exists).
