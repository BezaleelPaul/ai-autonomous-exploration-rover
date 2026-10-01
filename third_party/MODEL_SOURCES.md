# MODEL_SOURCES.md

Research record for the object-detection model survey. Created 2026-09-26 as
part of the repository audit + hardware audit + model research phase.

Evidence labels used throughout — **MEASURED** (ran on this host),
**VENDOR-CLAIMED** (taken from the publisher's own table, not verified here),
**SOURCE** (read from the model card / repo README), **UNKNOWN — MUST MEASURE**.

No candidate was chosen in advance; the shortlist was derived from the
requirements below and the benchmark decides the rest.

## 1. Constraints that filter the candidates (measured)

| Constraint | Value | Evidence |
|---|---|---|
| Host CPU | Intel Core i5-7300U @ 2.60 GHz, 2 cores / 4 threads | **MEASURED** `Win32_Processor` |
| Accelerator | none — `torch.cuda.is_available() == False`, `torch 2.12.0+cpu`, `torch.get_num_threads() == 2` | **MEASURED** |
| Realtime budget | `inference_interval (2) × p50 < 1.0 s` target-lock ⇒ **p50 must stay under 500 ms** | **MEASURED**, `tests/test_redteam_h4_realtime.py` |
| Current reference | `yolo11s.pt` @ 320 px, conf 0.25, min_box 8 → p50 **184 ms @50 % CPU load** (0.37 s refresh, H4 green); **534–685 ms @100 % load** (1.07–1.37 s, H4 red) | **MEASURED**, `logs/detection_baseline.json` (50 %), `logs/detection_final.json` + `logs/detection_cand_yolo11s.json` (100 %) |
| Camera | AI-Thinker ESP32-CAM, `FRAMESIZE_VGA` (640×480), `PIXFORMAT_JPEG`, `jpeg_quality=12`, `fb_count=2`, `xclk=20 MHz` | **SOURCE**, `esp32/camera_stream/camera_stream.ino:65-66` |
| Declared camera FPS | `fps_target: 15` | **SOURCE** (`config/config.yaml`) — actual stream FPS is **UNKNOWN — MUST MEASURE** |
| Recorded ESP32-CAM footage | **none** — 0 `.mp4/.avi/.mov/.mkv/.webm` anywhere in the repo; only `logs/webcam_annotated.jpg` and `logs/extcam.jpg` (webcam, not the ESP32) | **MEASURED** (repo-wide glob) |

Installed and relevant: `ultralytics 8.4.155`, `transformers 5.12.0`,
`onnxruntime 1.24.4`, `opencv 5.0.0`, `numpy 2.4.6`.
**Missing:** python `onnx` package, `openvino` (**MEASURED** `ModuleNotFoundError`).

## 2. Candidate shortlist (5 researched → 4 benchmarked)

| # | Model | Official source | License | Params | Local artifact | Load status |
|---|---|---|---|---|---|---|
| 1 | **YOLO26n** | https://github.com/ultralytics/ultralytics · https://huggingface.co/Ultralytics/YOLO26 · https://docs.ultralytics.com/models/yolo26 | **AGPL-3.0** or Ultralytics Enterprise | **2.57 M MEASURED** (vendor table says 2.4 M) | `yolo26n.pt` 5.29 MB **MEASURED** | **LOAD OK** |
| 2 | **YOLO11n** | https://github.com/ultralytics/ultralytics | **AGPL-3.0** or Enterprise | 2.6 M VENDOR-CLAIMED | `yolo11n.pt` 5.35 MB **MEASURED** | pre-existing, local |
| 3 | **YOLO11s** (current shipped incumbent) | https://github.com/ultralytics/ultralytics | **AGPL-3.0** or Enterprise | 9.4 M VENDOR-CLAIMED | `yolo11s.pt` 18.42 MB **MEASURED** | pre-existing, local |
| 4 | **RT-DETRv2-R18** | https://huggingface.co/PekingU/rtdetr_v2_r18vd · upstream https://github.com/lyuwenyu/RT-DETR (`rtdetrv2_pytorch`) · paper arXiv:2407.17140 | upstream **Apache-2.0**; HF card license **TO VERIFY** | **20.17 M MEASURED** (card says 20.2 M) | HF cache (auto-download) | **LOAD OK + FORWARD OK** |

YOLO26 / YOLO11 / YOLOv10 / YOLOv12 are all produced by the same upstream
project, so they share one license row in `THIRD_PARTY.md` — AGPL-3.0 is
already flagged there. Adding weights does not add a second license.

### Measured benchmark outcome (2026-09-26, all four shortlisted + incumbent)

| Candidate | Params (MEASURED) | Precision | Recall | F1 | Multi-obj | mAP@0.5 | Duplicates | p50 @97–100% load | Refresh | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **yolo11s (incumbent)** | 9.46 M | 0.8128 | **0.4769** | **0.6011** | **0.4711** | **0.6400** | 1 | 534 ms | 1.07 s | **KEEP — best of every eligible model** |
| yolo26s | 10.01 M | 0.7867 | 0.4726 | 0.5905 | 0.4667 | 0.5941 | 0 | 452 ms | 0.90 s | reject — dominated (slower, worse accuracy, more params) |
| yolo26n | 2.57 M | 0.8287 | 0.3541 | 0.4962 | 0.3490 | 0.5226 | 0 | 126 ms | 0.25 s | **low-power fallback** (4x realtime margin, −12.3 recall pts) |
| yolo11n | 2.62 M | 0.8051 | 0.3423 | 0.4804 | 0.3370 | 0.5161 | 0 | 124 ms | 0.25 s | reject — dominated by yolo26n at equal speed |
| RT-DETRv2-R18 | 20.17 M | 0.2828 | **0.8827** | 0.4284 | **0.8811** | **0.8145** | **283** | **3427 ms** | **6.85 s** | **rejected — realtime gate missed by 6.8x**, precision collapsed |

Full write-up, method, artefacts and reproduce commands:
**`reports/MODEL_BENCHMARK.md`**. Raw evidence in `logs/detection_cand_*.json`.
Result: **no model change**; `yolo11s` stays shipped, `yolo26n` recorded as
the measured low-power fallback.

### Per-candidate notes

**YOLO26n** — Ultralytics' January 2026 family. Vendor highlights: end-to-end
NMS-free inference, Distribution Focal Loss removed (claimed to simplify export
and speed CPU inference), ProgLoss + STAL for small objects, MuSGD optimizer.
Vendor table: mAP@50-95 40.9, CPU ONNX 38.9 ms @640, 5.5 GFLOPs
(**VENDOR-CLAIMED**, measured on their machine, not ours).
Verified here: `ultralytics 8.4.155` ships `cfg/models/26/yolo26.yaml`, so the
architecture is supported by the installed version (**MEASURED**); weight
downloads and constructs (**MEASURED**).

**YOLO11n** — same package, nano anchor point. Included so the sweep has a
like-for-like nano row instead of comparing only against the 9.4 M-param
incumbent. Weight was already in the repo.

**YOLO11s** — the currently shipped model. It is the reference row: any
candidate must beat it on measured accuracy *and* stay under the 500 ms p50
budget. Removing it would make the benchmark unfalsifiable.

**RT-DETRv2-R18** — the transformer/NMS-free arm of the comparison, so the
benchmark is not an intra-family contest. Different architecture class
(hybrid encoder + deformable decoder), so it tests whether NMS-free attention
helps on cluttered indoor frames. Included for **accuracy**; its latency is
already known to be out of budget (§4).

### Eliminated before benchmark (documented reasons)

| Candidate | Why it was cut |
|---|---|
| **YOLOv12n** | Attention/A2 blocks. Independent review (arXiv:2504.11995) reports YOLOv12-n slower on CPU than YOLO11-n at equal mAP, and Ultralytics' own comparison page flags "significantly slower CPU inference". Weight pulled to `yolo12n.pt` (5.34 MB) and kept as **reserve**; not granted one of the 4 slots. |
| **YOLOv10n** | Same NMS-free class as YOLO26n but superseded on paper (vendor mAP 39.5 vs 40.9) with no CPU figure to argue otherwise. Weight pulled (`yolov10n.pt` 5.59 MB), kept as **reserve**. |
| **NanoDet-Plus** (https://github.com/RangiLyu/nanodet) | Separate repo, own loader/post-processing — new integration surface for a vendor-claimed 27.0 mAP @320 (**VENDOR-CLAIMED**), below the incumbents. Integration cost exceeds expected gain. |
| **YOLO-World** (`yolov8s/m-worldv2.pt`, already local) | Open-vocabulary, not comparable on a closed-set COCO benchmark; upstream CC-BY-NC-4.0 already flagged **REVIEW** in `THIRD_PARTY.md`. |
| **facebook/detr-resnet-50** | Already **MEASURED** at 5.14 s/infer (`logs/benchmark_detr.json`) — ~50× over budget. Existing evidence, no reason to re-run. |
| YOLOv6 / YOLOv9 / PP-PicoDet / EfficientDet / FastestDet | No maintained path inside this repo's dependency set; each would need its own loader and post-processing. No evidence any is ahead of the shortlisted four. |

## 3. Compatibility issues found (measured, not assumed)

1. **`transformers 5.12.0` has no `RTDetrV2ImageProcessor`.** The class list is
   `RTDetrImageProcessor`, `RTDetrImageProcessorPil`, `RTDetrV2ForObjectDetection`,
   `RTDetrV2Config` — so the **v1** image-processor class must be used with the
   v2 model. `from transformers import RTDetrV2ImageProcessor` → `ImportError`.
2. Loading the RT-DETRv2 config prints
   *"You are using a model of type `rt_detr_v2` to instantiate a model of type `rt_detr`"*
   — a real warning, harmless here but it must not be swallowed silently.
3. `post_process_object_detection(target_sizes=...)` needs a **list of `(h, w)`
   tuples**. Passing a flat tuple raises
   `ValueError: Make sure that you pass in as many target sizes as the batch dimension of the logits`.
   (First forward attempt failed on exactly this.)
4. **python `onnx` was missing while `onnxruntime 1.24.4` was present**, and
   `openvino` was absent entirely — so Ultralytics `model.export(format="onnx")`
   could not run. **RESOLVED 2026-09-26:** `onnx 1.23.0` and `openvino 2026.4.0`
   were installed and the runtime axis was measured (§4, §5). Neither package is
   a runtime dependency of the rover: they are **export-only tooling**, installed
   with `py -3.12 -m pip install onnx openvino`, which is why neither is listed
   in `requirements.txt` (adding them there would break the
   "every requirements.txt entry must be imported by code" consistency test).
5. **RT-DETRv2 is pinned to 640×640** by its own documentation ("reshaping to
   other sizes will generally degrade performance"), so it cannot use the
   rover's 320 px setting. Measured at 640: **p50 2463 ms** (min 1943, max 3525)
   **MEASURED** — ~23× the reference and ~5× the 500 ms gate.
6. **No code change needed for the YOLO arm.** `create_detector(cfg)` dispatches
   on `ai.backend` / `ai.yolo_model` (`software/ai/detector.py:294-316`), and
   `scripts/eval_detection.py` already accepts `--set`, so candidates run
   through the existing harness unchanged.

## 4. Benchmark plan — EXECUTED 2026-09-26

**Dataset:** `datasets/coco128/` — 128 labelled images / 929 objects / 71
classes / 114 images with ≥2 objects. It is the **only** labelled data in the
repo. All accuracy numbers are therefore an **OFFLINE PROXY**; on-robot
confirmation is **NOT YET MEASURED** and needs the camera collection tool below.

**Runs (executed — 4 candidates + incumbent, same dataset, same settings):**

```
py -3.12 scripts/eval_detection.py --out logs/detection_cand_yolo11s.json   # incumbent baseline row
py -3.12 scripts/eval_detection.py --set ai.yolo_model=<weight> --out logs/detection_cand_<candidate>.json
# HF backend needs BOTH sets (ai.model_dir outranks ai.model_name):
py -3.12 scripts/eval_detection.py --set ai.backend=hf --set ai.model_name=PekingU/rtdetr_v2_r18vd --set ai.model_dir= --out logs/detection_cand_rtdetrv2_r18.json
```

**Per candidate, recorded:** precision, recall, F1, multi-object recall,
duplicate detections, mAP@0.5 (all implemented in
`software/ai/detection_metrics.py`), plus p50/p95 latency, explicit CPU-load
reading and the H4 closure check. `scripts/eval_detection.py` also reports
model load time and detection count. **Preprocessing/postprocessing split and
frame age remain UNKNOWN — NOT YET MEASURED** (not implemented in the harness).

**Runtime axis:** **MEASURED for all three runtimes — EXECUTED 2026-09-26.**
Matched 160-frame runs of the same `yolo11s` weights at `imgsz 320`, all at
100% CPU load:

| Runtime | p50 | p95 | Refresh | vs PyTorch |
|---|---:|---:|---:|---|
| PyTorch (`yolo11s.pt`, shipped) | 435 ms | 982 ms | 0.87 s | — |
| **ONNX Runtime** (`yolo11s.onnx`) | **181 ms** | **290 ms** | **0.36 s** | **2.4× faster** |
| OpenVINO 2026.4.0 | 461 ms | 1060 ms | 0.92 s | 1.06× **slower** |

Artifacts: `logs/detection_yolo11s_pt.json`, `_yolo11s_onnx.json`,
`_yolo11s_openvino.json`. Full analysis in `reports/MODEL_BENCHMARK.md` §6.
**Conclusion: adopt ONNX for realtime headroom; OpenVINO is a measured
regression on this host — do not use it here.** Accuracy columns are identical
between the two exports (both fp32); the shipped `.pt` differs by 0.7–1.3
points and stores its weights in `torch.float16` (MEASURED), but the causal
link to the accuracy shift is **NOT YET MEASURED**.

**Blocked until footage exists (all NOT YET MEASURED):** camera FPS, decoded
FPS, dropped frames, frame age, network latency, end-to-end latency,
false-positive rate on real scenes, the pillow/person red-team set, and any
train/val/test split (scene-level separation is impossible without multiple
recorded scenes).

**Tooling:** `scripts/collect_camera_dataset.py` is **BUILT** (ESP32-CAM /
webcam / mock capture across the 15 listed lighting, position and occlusion
conditions, `manifest.csv`, optional YOLO auto-labels explicitly marked
`model_prediction (NOT ground truth)`) — but **never run against real
hardware yet**, so every camera-side metric above stays NOT YET MEASURED. The
pre/post-processing latency split is still **not implemented** in the harness.
Model code is explicitly **not** to be written before those steps.

## 5. Deliverables status

| Deliverable | State |
|---|---|
| `third_party/MODEL_SOURCES.md` | **this file** |
| `reports/MODEL_BENCHMARK.md` | **done** — written from the measured runs, incl. §6 runtime axis |
| `logs/detection_cand_*.json` | **done** — 5 runs (`yolo11s`, `yolo26s`, `yolo26n`, `yolo11n`, `rtdetrv2_r18`) |
| `logs/detection_yolo11s_{pt,onnx,openvino}.json` | **done** — matched 160-frame runtime runs |
| `scripts/collect_camera_dataset.py` | **BUILT** — 15 conditions, `esp32`/`webcam`/`mock` sources, `manifest.csv`, auto-labels marked as model predictions; **never yet run on hardware** |
| `docs/MODEL_SELECTION.md` | **done** — selection rule, measured table, load + runtime caveats, not-measured table |
| Pillow/person red-team suite | **NOT YET BUILT** — requires recorded footage |
