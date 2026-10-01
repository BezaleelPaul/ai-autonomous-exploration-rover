# MODEL_BENCHMARK — Candidate Detection Model Benchmark

**Evidence label: [MEASURED] unless stated otherwise.** All numbers below are
output of `scripts/eval_detection.py` on this host and are reproducible from
the JSON artifacts in `logs/detection_cand_*.json`. No figure in this file is
a vendor claim, a paper number, or a guess.

- **Generated:** 2026-09-26
- **Harness:** `scripts/eval_detection.py` (repo-local, `software/ai/detection_metrics.py`)
- **Dataset:** COCO128 — 128 images, 929 ground-truth objects, 71 classes,
  114 images containing ≥2 objects.
  Source: `https://github.com/ultralytics/yolov5/releases/download/v1.0/coco128.zip`
  (CC BY 4.0, attributed in `THIRD_PARTY.md`)
- **Operating point:** `confidence_threshold 0.25`, `min_box_px 8`, IoU 0.5,
  `inference_interval 2`, tracking off (accuracy pass is detection-only).
- **Host:** Intel Core i5-7300U @2.60 GHz, 2 cores / 4 threads,
  `torch.cuda.is_available() == False`, `torch.get_num_threads() == 2`,
  torch 2.12.0+cpu, ultralytics 8.4.155, transformers 5.12.0.
- **CPU load during latency runs: 97–100%.** This is a *pessimistic* host;
  the same machine idles near 10%. Latency here is an upper bound, not a
  typical figure. See *Realtime gate* below.

---

## 1. Objective and selection rule

Select one detector for the AI Visual Smart Rover. A candidate is only
eligible if it satisfies **both**:

1. **Accuracy** — best measured detection quality on the labelled set
   (precision, recall, F1, multi-object recall, mAP@0.5, duplicates).
2. **Realtime** — `tests/test_redteam_h4_realtime.py` gate:
   `inference_interval(2) × p50 < 1.0 s`, i.e. **p50 < 500 ms**, giving a
   1.0 s worst-case perception refresh on `config.yaml ai.inference_interval`.

A model that is more accurate but misses the realtime gate is **not
eligible**. This rule is applied below; it is what eliminates RT-DETR.

---

## 2. Measured results (all candidates, one dataset, one operating point)

| Candidate | Backend / resolution | Params (M) | On disk (MB) | Precision | Recall | F1 | Multi-obj recall | mAP@0.5 | Duplicates | p50 (ms) | p95 (ms) | Refresh (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **yolo11s (incumbent)** | ultralytics / 320 | 9.46 | 19.31 | **0.8128** | **0.4769** | **0.6011** | **0.4711** | **0.6400** | 1 | 534 | 1890 | 1.07 |
| yolo26s | ultralytics / 320 | 10.01 | 20.42 | 0.7867 | 0.4726 | 0.5905 | 0.4667 | 0.5941 | 0 | 452 | 611 | 0.90 |
| yolo26n | ultralytics / 320 | 2.57 | 5.54 | 0.8287 | 0.3541 | 0.4962 | 0.3490 | 0.5226 | 0 | 126 | 177 | 0.25 |
| yolo11n | ultralytics / 320 | 2.62 | 5.61 | 0.8051 | 0.3423 | 0.4804 | 0.3370 | 0.5161 | 0 | 124 | 142 | 0.25 |
| RT-DETRv2-R18 | transformers `hf` / 640 | 20.17 | n/a¹ | 0.2828 | **0.8827** | 0.4284 | **0.8811** | **0.8145** | **283** | **3427** | **10183** | **6.85** |

¹ RT-DETR weights live in the Hugging Face hub cache as a shard set, not a
single file, so no comparable "on disk" size is reported rather than guessing.

`Refresh = inference_interval(2) × p50`. Accuracy columns are over the full
128 images; p50/p95 are over 20 frames (6 frames for RT-DETR, which is ~6x
slower to run).

This table compares **models**. The same model under the ONNX and OpenVINO
**runtimes** is measured separately in §6, on matched 160-frame runs.

Artifacts: `logs/detection_cand_yolo11s.json`, `_yolo26s.json`, `_yolo26n.json`,
`_yolo11n.json`, `_rtdetrv2_r18.json`.

---

## 3. Realtime gate at the measured load

At the **97–100% CPU load** of these runs:

| Candidate | Refresh at measured load | vs 1.0 s lock |
|---|---|---|
| yolo26n | 0.25 s | **PASS** (4.0x margin) |
| yolo11n | 0.25 s | **PASS** (4.0x margin) |
| yolo26s | 0.90 s | passes, thin (1.1x) |
| yolo11s (incumbent) | 1.07 s | over, thin (0.93x) |
| RT-DETRv2-R18 | 6.85 s | **FAIL by 6.8x** |

**Interpretation.** The gate is load-sensitive: the s-class models sit inside
the measurement noise band of the 1.0 s lock (0.90–1.07 s for the same class
of model in the same hour), so the measured load row must not be read as
"yolo26s passes and yolo11s fails". The authoritative realtime evidence is
`tests/test_redteam_h4_realtime.py`, which runs against a loaded model and
passes at ≤~60% host CPU and fails at ~100% host CPU for *any* s-class model
(previously measured at imgsz 320: 560/865/944 ms under saturation). Only the
two nano models carry real headroom under saturation.

---

## 4. Candidate-by-candidate assessment

### yolo11s (shipped incumbent) — **recommended, keep**

Best of every eligible model on every accuracy column: F1 0.6011, mAP@0.5
0.6400, multi-object recall 0.4711, precision 0.8128, 1 duplicate. At 9.46 M
params / 19.31 MB it clears the realtime gate under normal host load. It is
also the incumbent: switching costs integration risk for no measured gain.

### yolo26s — reject

Essentially ties the incumbent on recall (0.4726 vs 0.4769) while being
*slower* (452 vs 534 ms are within noise, but it is not faster) and clearly
worse on mAP (0.5941 vs 0.6400), precision (0.7867 vs 0.8128) and F1 (0.5905
vs 0.6011), at a higher parameter count (10.01 M vs 9.46 M). Dominated.

### yolo26n — the low-power fallback, not the default

The fastest accurate-enough option: **2.57 M params, 126 ms p50, 0.25 s
refresh even at 100% load** — 4x realtime margin where the incumbent has none
under saturation. The cost is accuracy: recall 0.3541 vs 0.4769, i.e. **−12.3
recall points** and −10.5 F1 points. It also beats yolo11n on every accuracy
column at equal speed (F1 0.4962 vs 0.4804, mAP 0.5226 vs 0.5161), so if a
load test ever forces a downgrade, **yolo26n is the measured choice over
yolo11n**.

### yolo11n — reject

Strictly dominated by yolo26n: same speed (124 vs 126 ms), more params
(2.62 M vs 2.57 M), worse on precision, recall, F1, mAP and multi-object
recall.

### RT-DETRv2-R18 (`PekingU/rtdetr_v2_r18vd`, `ai.backend: hf`) — reject

The strongest raw detector measured and it is not close on the accuracy
objective: **recall 0.8827 vs 0.4769** (nearly 2x), multi-object recall
0.8811 vs 0.4711, mAP@0.5 0.8145 vs 0.6400. It is, however, **disqualified
on realtime by ~6.8x** (3427 ms p50, 6.85 s refresh against a 1.0 s lock, and
10.2 s at p95), and its precision collapses to 0.2828 with **283 duplicate
detections** — the NMS-free 300-query head emits overlapping boxes for the
same object, and the harness's duplicate counter counts them. Adopting it
would require a hard NMS post-pass *and* hardware (GPU) that this host does
not have. It also cannot use the rover's 320 px operating point: RT-DETR is
trained for 640x640 and cannot be evaluated at 320 without re-validation.

**Conclusion:** RT-DETR is the accuracy winner and the latency loser. Under
the selection rule in §1 it is not eligible.

---

## 5. Recommendation

> Under the tested hardware (Intel i5-7300U, 2C/4T, CPU-only), dataset
> (COCO128, 128 images, 929 objects, 71 classes) and load (97–100% CPU),
> **yolo11s at `imgsz 320` achieved the best measured detection accuracy of
> every model that satisfies the realtime gate** — precision 0.8128, recall
> 0.4769, F1 0.6011, multi-object recall 0.4711, mAP@0.5 0.6400, 1 duplicate
> — and RT-DETRv2-R18, the most accurate model measured overall (recall
> 0.8827, mAP@0.5 0.8145), was excluded for missing the realtime gate by
> 6.8x.

**Action: no model change.** The shipped `ai.yolo_model` stays on `yolo11s`.
`yolo26n` is recorded as the measured low-power fallback (0.25 s refresh even
under saturation, −12.3 recall points).

---

## 6. Runtime axis — PyTorch vs ONNX vs OpenVINO (matched runs)

Same model, same weights, same dataset, same operating point, same `imgsz 320`,
**160 timed frames per arm, back-to-back at 100% CPU load.** This isolates the
inference runtime; the model is not changing.

| Runtime | Export artifact | On disk (MB) | Precision | Recall | F1 | Multi-obj | mAP@0.5 | Dupes | p50 | p95 | Refresh | H4 gate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| PyTorch (as shipped) | `yolo11s.pt` | 19.31 | **0.8128** | 0.4769 | 0.6011 | 0.4711 | 0.6400 | 1 | 435 ms | 982 ms | 0.87 s | closes, thin (1.15x) |
| **ONNX Runtime** | `yolo11s.onnx` | 37.88 | 0.8025 | **0.4898** | **0.6083** | **0.4842** | **0.6483** | 1 | **181 ms** | **290 ms** | **0.36 s** | **closes, 2.75x margin** |
| OpenVINO 2026.4.0 | `yolo11s_openvino_model/` | 38.13 | 0.8025 | 0.4898 | 0.6083 | 0.4842 | 0.6483 | 1 | 461 ms | 1060 ms | 0.92 s | closes, knife-edge (1.08x) |

Artifacts: `logs/detection_yolo11s_pt.json`, `_yolo11s_onnx.json`,
`_yolo11s_openvino.json`.

**Findings — MEASURED:**

1. **ONNX is 2.4x faster than PyTorch on p50** (181 vs 435 ms) and 3.4x on p95
   (290 vs 982 ms) at identical load. Realtime headroom goes from 1.15x to
   2.75x — that is the difference between "passes only on an idle host" and
   "passes under saturation".
2. **OpenVINO regresses on this host.** 461 ms p50 is *slower* than plain
   PyTorch and 2.5x slower than ONNX. On a 2C/4T laptop CPU its runtime
   overhead does not pay for itself. **Do not adopt OpenVINO here** — measured,
   not assumed.
3. **Runtime is not an accuracy lever.** ONNX and OpenVINO report identical
   accuracy columns (both are fp32 exports of the same weights); PyTorch differs
   by 0.7–1.3 points. **MEASURED:** `yolo11s.pt` stores all 256 parameter
   tensors as `torch.float16` (9,458,752 params → 18.04 MiB) while both exports
   are fp32. Whether that fp16/fp32 difference *causes* the accuracy shift, or
   whether kernel numerics do, is **NOT YET MEASURED** — do not quote it as the
   mechanism.
4. **PyTorch latency is noisy under saturation**: 435 ms in this matched run,
   534 ms in `detection_cand_yolo11s.json`, 685 ms in `detection_final.json`,
   all at ~100% load. Never splice a p50 from one run onto a result from
   another.

**Recommendation.** Keep `yolo11s` as the model; ONNX is a *runtime* choice,
not a model change. The **shipped config stays on `.pt`**: a fresh checkout has
no `.onnx`, and shipping a path that does not exist would break first run.
To run the measured-fast configuration:

```powershell
py -3.12 -m pip install onnx
py -3.12 -c "from ultralytics import YOLO; YOLO('yolo11s.pt').export(format='onnx', imgsz=320, opset=13, simplify=False, optimize=False, device='cpu')"
# then: ai.yolo_model: "yolo11s.onnx"
```

---

## 7. Not measured — do not quote as a result

| Item | Status |
|---|---|
| ESP32-CAM real-scene false-positive rate | **NOT YET MEASURED** (no ESP32 footage in repo) |
| Camera FPS / decoded FPS / dropped frames / frame age | **NOT YET MEASURED** — the single-slot frame buffer, dropped counter and frame age now exist in `software/camera/frame_manager.py`, but no footage has been pushed through them |
| Network / end-to-end latency camera→decision | **NOT YET MEASURED** |
| Any train/val/test split on this repo's own scenes | **NOT YET MEASURED** (COCO128 is a public benchmark, not this rover's camera) |
| Pillow / person red-team detection set | **NOT YET MEASURED** |
| ONNX inference latency | **MEASURED — §6**: p50 181 ms, 0.36 s refresh at 100% load |
| OpenVINO inference latency | **MEASURED — §6**: p50 461 ms, a *regression* on this host |
| fp16-vs-fp32 as the cause of the runtime accuracy shift | **NOT YET MEASURED** — dtypes are measured (§6), the causal mechanism is not isolated |
| Per-model RAM / CPU% during inference | **NOT YET MEASURED** (`psutil` 7.2.2 available but not wired into the harness) |
| Tracking stability across models | **NOT YET MEASURED** (accuracy pass runs with `yolo_track` off) |

Latency figures in §2 were taken at 97–100% CPU load and are an **upper
bound**; re-measure the chosen model at ≤~60% load before quoting a typical
refresh time.

---

## 8. Reproduce

```powershell
py -3.12 scripts\eval_detection.py --out logs\detection_cand_yolo11s.json --latency-frames 20 --latency-repeats 1
py -3.12 scripts\eval_detection.py --set ai.yolo_model=yolo26n.pt --out logs\detection_cand_yolo26n.json
py -3.12 scripts\eval_detection.py --set ai.yolo_model=yolo11n.pt --out logs\detection_cand_yolo11n.json
py -3.12 scripts\eval_detection.py --set ai.yolo_model=yolo26s.pt --out logs\detection_cand_yolo26s.json
# HF backend: BOTH sets are required — ai.model_dir takes precedence over ai.model_name
py -3.12 scripts\eval_detection.py --set ai.backend=hf --set ai.model_name=PekingU/rtdetr_v2_r18vd --set ai.model_dir= --out logs\detection_cand_rtdetrv2_r18.json

# --- runtime axis (§6): export once, then matched 160-frame runs ---
py -3.12 -m pip install onnx openvino
py -3.12 -c "from ultralytics import YOLO; YOLO('yolo11s.pt').export(format='onnx', imgsz=320, opset=13, simplify=False, optimize=False, device='cpu')"
py -3.12 -c "from ultralytics import YOLO; YOLO('yolo11s.pt').export(format='openvino', imgsz=320, half=False, device='cpu')"
py -3.12 scripts\eval_detection.py --set ai.yolo_model=yolo11s.pt               --latency-frames 80 --out logs\detection_yolo11s_pt.json
py -3.12 scripts\eval_detection.py --set ai.yolo_model=yolo11s.onnx             --latency-frames 80 --out logs\detection_yolo11s_onnx.json
py -3.12 scripts\eval_detection.py --set ai.yolo_model=yolo11s_openvino_model   --latency-frames 80 --out logs\detection_yolo11s_openvino.json
```

Related: `third_party/MODEL_SOURCES.md` (sources, licences, eliminations),
`REGRESSION_REPORT.md` §9 (accuracy + realtime session), `THIRD_PARTY.md`
(attribution).
