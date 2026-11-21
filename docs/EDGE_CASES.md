# Edge-case evaluation

A single mAP number hides the failures that matter on a rover: a person at 4 m,
a dark corridor, chairs pushed together, motion blur when the wheels slip. The
24-class training kernel therefore evaluates the same checkpoint on several
**stress buckets** and reports the drop against the clean validation split.

The numbers live in `edge_cases.json` (produced by `kaggle/coco24/rover24_train.py`)
and are summarised in [`../models/MODEL_CARD.md`](../models/MODEL_CARD.md).

---

## Buckets

| Bucket | Definition | Why it matters |
|---|---|---|
| `baseline` | Full COCO val2017 split used for training validation | reference mAP |
| `small` | ≥ 60 % of ground-truth boxes have area < 32² px | distant objects; 320 px input loses detail |
| `dark` | mean image luminance < 60 (0–255) | corridors, evening, underexposed phone camera |
| `cluttered` | any two ground-truth boxes overlap with IoU > 0.2 | furniture clusters; NMS and occlusion |
| `blurred` | Gaussian blur, 5 × 5 kernel, σ = 2.5 | motion blur from vibration/acceleration |

Up to 500 images per bucket, all drawn from the **same** val2017 pool so the
comparison is like-for-like. Every bucket is scored with the same weights,
`imgsz=320`, and Ultralytics' standard mAP implementation.

---

## Measured result (rover24, 2026-11-17)

| Bucket | Images | mAP50 | mAP50-95 | Recall | Δ mAP50 |
|---|---|---|---|---|---|
| baseline | 3,964 | 0.343 | 0.225 | 0.339 | — |
| small | 500 | **0.173** | 0.102 | 0.186 | **−0.170** |
| dark | 178 | 0.349 | 0.202 | 0.305 | +0.005 |
| cluttered | 500 | 0.304 | 0.198 | 0.295 | −0.039 |
| blurred | 250 | 0.381 | 0.274 | 0.420 | +0.038 |

Reading it:

* **Small objects are the weak spot** — mAP halves. That is expected at 320 px
  and is the one number to act on: run at 416/512 when there is CPU headroom,
  approach slowly, and keep the sonar gate as the hard stop.
* **Dark** shows no penalty on this bucket, but 178 images is a small sample;
  do not claim night robustness from it.
* **Clutter** costs ~4 points — acceptable, and the area brake backs it up.
* **Blur** scores higher than baseline. With only 250 random images versus
  3,964, that is a bucket-composition effect, not evidence that blur helps.
  Report it honestly as "no measurable penalty at σ=2.5".

The raw numbers are in `edge_cases.json` in the trained bundle and in
`models/edge_cases.json`.

Rule of thumb for this project:

| Drop vs baseline | Interpretation |
|---|---|
| < 5 points | robust enough for the demo |
| 5–15 points | visible but acceptable; tune confidence / lighting |
| > 15 points | do not rely on it in that condition; fix the data or the approach |

### If a bucket is weak, the fix is specific

| Weak bucket | Mitigation |
|---|---|
| `small` | run inference at 416/512 on the laptop; approach targets more slowly; add distance-aware braking |
| `dark` | collect low-light frames; raise `hsv_v` augmentation; add a light ring |
| `cluttered` | lower NMS IoU / raise confidence; rely on the area brake and the ultrasonic gate |
| `blurred` | add motion blur to training augmentation; reduce acceleration; the gate remains the hard stop |

---

## What this does **not** prove

* It is still COCO imagery, not the rover's own camera. In-domain frames from
  `scripts/collect_dataset.py` remain the real test.
* The buckets are proxies: "dark" is luminance, not glare; "cluttered" is box
  overlap, not true occlusion.
* No model is accurate on every object. The hard safety layer is the ultrasonic
  gate + watchdogs; vision is advisory and is allowed to be wrong.

---

## Reproduce

```bash
make kaggle-coco24
make kaggle-status24
make kaggle-download24
python scripts/install_model.py /tmp/ai-rover-model/rover24_bundle.zip
```

The kernel writes `edge_cases.json` into the bundle and removes the prepared
images before exiting, so the Kaggle output stays small.
