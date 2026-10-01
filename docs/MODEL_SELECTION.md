# Model Selection

**Decision: keep `yolo11s.pt` at `imgsz 320`. No model change.**
`yolo26n.pt` is the recorded low-power fallback. The measured-fastest
*runtime* for those same weights is ONNX (2.4× faster p50, §4); the shipped
config stays on `.pt` so a fresh checkout runs without an export step.

Every number on this page is **[MEASURED]** on this host against labelled data.
The full method, per-candidate analysis and reproduce commands live in
[`reports/MODEL_BENCHMARK.md`](../reports/MODEL_BENCHMARK.md); sources,
licences and eliminated candidates live in
[`third_party/MODEL_SOURCES.md`](../third_party/MODEL_SOURCES.md).

---

## 1. Selection rule

A candidate is eligible only if it satisfies **both**:

1. **Accuracy** — best measured precision, recall, F1, multi-object recall and
   mAP@0.5 on the labelled set.
2. **Realtime** — `tests/test_redteam_h4_realtime.py`: `inference_interval(2) × p50 < 1.0 s`,
   i.e. **p50 < 500 ms**, so worst-case perception refresh stays under 1.0 s.

More accurate but slower does **not** win. That rule is what eliminates
RT-DETRv2.

## 2. Measured results

Dataset: COCO128 — 128 images / 929 objects / 71 classes / 114 multi-object
images. Operating point: `confidence_threshold 0.25`, `min_box_px 8`, IoU 0.5.
Host: Intel Core i5-7300U, 2C/4T, CPU-only (torch 2.12.0+cpu), **CPU load
97–100 % during latency runs** — an upper bound, not a typical figure.

| Candidate | Params | Precision | Recall | F1 | Multi-obj | mAP@0.5 | Dupes | p50 | Refresh | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **yolo11s (shipped)** | 9.46 M | 0.8128 | **0.4769** | **0.6011** | **0.4711** | **0.6400** | 1 | 534 ms | 1.07 s | **SELECTED** |
| yolo26s | 10.01 M | 0.7867 | 0.4726 | 0.5905 | 0.4667 | 0.5941 | 0 | 452 ms | 0.90 s | dominated |
| yolo26n | 2.57 M | 0.8287 | 0.3541 | 0.4962 | 0.3490 | 0.5226 | 0 | 126 ms | 0.25 s | **fallback** |
| yolo11n | 2.62 M | 0.8051 | 0.3423 | 0.4804 | 0.3370 | 0.5161 | 0 | 124 ms | 0.25 s | dominated by yolo26n |
| RT-DETRv2-R18 | 20.17 M | 0.2828 | **0.8827** | 0.4284 | **0.8811** | **0.8145** | **283** | **3427 ms** | **6.85 s** | **rejected** |
| **yolo11s → ONNX runtime** † | 9.46 M | 0.8025 | 0.4898 | 0.6083 | 0.4842 | 0.6483 | 1 | **181 ms** | **0.36 s** | **fastest measured runtime** |
| yolo11s → OpenVINO runtime † | 9.46 M | 0.8025 | 0.4898 | 0.6083 | 0.4842 | 0.6483 | 1 | 461 ms | 0.92 s | rejected — slower than PyTorch |

† Same weights, different inference runtime — a matched **160-frame** run where
the model rows above are 20-frame runs. Full table and caveats in
[`reports/MODEL_BENCHMARK.md`](../reports/MODEL_BENCHMARK.md) §6.

## 3. Why each candidate was chosen or cut

**yolo11s — selected.** Best of every eligible model on every accuracy column,
9.46 M params, and it is the incumbent, so switching would buy no measured gain
while adding integration risk.

**yolo26s — cut.** Ties the incumbent on recall while being worse on mAP
(0.5941 vs 0.6400), precision (0.7867 vs 0.8128) and F1, at a higher parameter
count (10.01 M vs 9.46 M). Dominated.

**yolo26n — recorded fallback.** 2.57 M params, p50 126 ms, **0.25 s refresh
even at 100 % CPU load** (4× realtime margin where the incumbent has none under
saturation). Costs **−12.3 recall points** (0.3541 vs 0.4769) and −10.5 F1
points. It also beats yolo11n on every accuracy column at equal speed, so if
the realtime gate ever cannot be met, **yolo26n is the measured choice**.

**yolo11n — cut.** Strictly dominated by yolo26n: same speed, more params,
worse on precision, recall, F1, mAP and multi-object recall.

**RT-DETRv2-R18 — rejected.** The most accurate detector measured (recall
0.8827, mAP@0.5 0.8145 — nearly 2× the incumbent's recall) but **disqualified
on realtime by ~6.8×** (3427 ms p50, 6.85 s refresh against a 1.0 s lock,
10.2 s at p95). Its precision also collapses to 0.2828 with **283 duplicate
detections** from the NMS-free 300-query head, and RT-DETR is fixed at
640×640 — it cannot use the rover's 320 px operating point without
re-validation. Adopting it would need NMS post-processing *and* GPU hardware
this host does not have.

## 4. Realtime is load-sensitive — this is the operative caveat

| Host CPU load | yolo11s p50 | Refresh (×2) | H4 gate |
|---|---:|---:|---|
| 50 % (`logs/detection_baseline.json`) | 184 ms | 0.37 s | **green** |
| 97–100 % (`logs/detection_cand_yolo11s.json`) | 534 ms | 1.07 s | red |
| 100 % (`logs/detection_final.json`) | 685 ms | 1.37 s | red |

The **runtime** moves this picture as much as the load does. Matched 160-frame
runs of the *same weights* at `imgsz 320`, all at 100 % load:

| Runtime | p50 | Refresh (×2) | H4 gate |
|---|---:|---:|---|
| PyTorch (`yolo11s.pt`, shipped) | 435 ms | 0.87 s | green, thin (1.15×) |
| **ONNX Runtime (`yolo11s.onnx`)** | **181 ms** | **0.36 s** | **green, 2.75× margin** |
| OpenVINO (`yolo11s_openvino_model/`) | 461 ms | 0.92 s | green, knife-edge (1.08×) |

**Run `pytest tests\test_redteam_h4_realtime.py` with the host at ≤~60 % load.**
With the shipped PyTorch runtime on a saturated host even imgsz 320 fails
(anywhere in 435–685 ms across runs), and 416/480 fail at any load — which
is why the +20.7 recall points at imgsz 480 were given up. ONNX is the one
measured way to hold realtime under saturation without giving up accuracy.

## 5. How to switch models

Config only — no navigation, safety or serial code changes:

```yaml
ai:
  yolo_model: "yolo26n.pt"   # measured fallback
  yolo_imgsz: 320
  backend: "yolo"            # yolo | hf | color | mock
```

For the HF backend set **both** keys — `ai.model_dir` takes precedence over
`ai.model_name`, and `HFDetector` now warns when it shadows a mismatched name:

```powershell
py -3.12 scripts\eval_detection.py --set ai.backend=hf --set ai.model_name=PekingU/rtdetr_v2_r18vd --set ai.model_dir=
```

**To run the measured-fastest runtime** (2.4× faster p50 than PyTorch, same
weights) — the export is one step and the `.onnx` file does not exist in a
fresh checkout, which is why the shipped config stays on `.pt`:

```powershell
py -3.12 -m pip install onnx
py -3.12 -c "from ultralytics import YOLO; YOLO('yolo11s.pt').export(format='onnx', imgsz=320, opset=13, simplify=False, optimize=False, device='cpu')"
```

then set `ai.yolo_model: "yolo11s.onnx"`. OpenVINO is measurable the same way
and **measured slower on this host — do not switch to it**.

## 6. Not measured — do not treat as a result

| Item | Status |
|---|---|
| ESP32-CAM real-scene false-positive rate | **NOT YET MEASURED** — needs `scripts/collect_camera_dataset.py` |
| Camera FPS / decoded FPS / dropped frames / frame age | **NOT YET MEASURED** — buffer + age counters now exist in `software/camera/frame_manager.py`, but no footage has been pushed through them |
| Network / end-to-end camera→decision latency | **NOT YET MEASURED** |
| ONNX runtime comparison | **MEASURED** — p50 181 ms vs PyTorch 435 ms at 100 % load (matched 160-frame runs); see §4 and `reports/MODEL_BENCHMARK.md` §6 |
| OpenVINO runtime comparison | **MEASURED** — p50 461 ms, a *regression* vs PyTorch on this 2C/4T host |
| fp16-vs-fp32 as the cause of the small runtime accuracy shift | **NOT YET MEASURED** — weight dtypes are measured, the causal link is not |
| Train/val/test split on this rover's own scenes | **NOT YET MEASURED** — COCO128 is a public benchmark, not this camera |
| Pillow / person red-team detection set | **NOT YET MEASURED** — requires recorded footage |
| Per-model RAM / CPU% during inference | **NOT YET MEASURED** |
| Tracking stability across models | **NOT YET MEASURED** — accuracy pass runs with `yolo_track` off |

Evidence labels used throughout this repo: **[MEASURED]**, **VENDOR-CLAIMED**,
**SOURCE**, **UNKNOWN — MUST MEASURE**, **SIMULATED**, **HARDWARE REQUIRED**.
Nothing on this page is a vendor claim.
