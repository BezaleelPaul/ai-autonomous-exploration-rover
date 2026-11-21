# Training the rover's vision model

Full Kaggle walkthrough: [`../kaggle/README.md`](../kaggle/README.md).
This page is the short operational version.

---

## The pipeline

```
rover camera ──► collect_dataset.py ──► datasets/raw
                                          │
                              prepare_dataset.py (validate + split + zip)
                                          │
                                    datasets/rover.zip
                                          │
                            Kaggle dataset + rover_finetune.ipynb (GPU)
                                          │
                          best.pt / OpenVINO FP16 / ONNX
                                          │
                              config/rover.json → weights
```

---

## 1. Collect

```bash
python scripts/collect_dataset.py \
    --camera http://192.168.4.2:8080/video \
    --interval 0.6 --max-frames 400 --auto-label
```

Auto-labelling uses stock COCO YOLO11n, so it can only propose the six default
classes. **Review the labels** — 20 minutes of correction is worth 10 mAP points.

Class list (change in `software/ai_rover/dataset.py`):

```
person, chair, table, backpack, bottle, plant
```

COCO mapping is already handled: `dining table → table`, `potted plant → plant`.

### Coverage checklist

- [ ] 300+ images (500–800 is better)
- [ ] 3+ rooms
- [ ] daylight + artificial light + one dim scene
- [ ] each object at ~0.3 m, ~1 m, ~3 m
- [ ] some partially occluded objects
- [ ] ~10 % background/empty frames
- [ ] camera at the real mounting height, not held in your hand

---

## 2. Package

```bash
python scripts/prepare_dataset.py --raw datasets/raw --out datasets/rover --val 0.15 --zip
```

The output tells you exactly what will hurt training:

```
images: 412
labelled_images: 401
empty_images: 11
boxes: 1387
invalid_lines: 0
per_class: {0: 640, 1: 380, 2: 210, 3: 90, 4: 52, 5: 15}
WARNING: no boxes for classes: ['plant']
```

A class with < 50 boxes will drag the average down — either collect more or drop
it from `ROVER_CLASSES` and re-run.

---

## 3. Train on Kaggle

1. Upload `datasets/rover.zip` as a dataset (`ai-rover-detection`).
2. Import `kaggle/rover_finetune.ipynb`.
3. Attach the dataset, enable **GPU T4** and **Internet**.
4. Run all (~20–35 min).

Settings that matter:

| Setting | Value | Why |
|---|---|---|
| `imgsz` | 320 | matches inference; 4× cheaper than 640 |
| `lr0` | 0.002 | fine-tune rate |
| `epochs` | 60 | with early stopping at 15 |
| `batch` | -1 (auto) | 16 on a 16 GB GPU |
| `mosaic` | 0.8, closed for 10 epochs | small dataset, real framing |
| `fliplr` | 0.5 | safe for obstacle classes |
| `freeze` | 0 or 10 | 10 for < 300 images |

Terminal alternative (same GPU box):

```bash
python kaggle/train_rover.py --data /kaggle/input/ai-rover-detection --epochs 60
```

---

## 4. Judge the model honestly

| Metric | Minimum | Good | Meaning |
|---|---|---|---|
| mAP50 | 0.55 | 0.75+ | "finds the object at all" |
| mAP50-95 | 0.30 | 0.45+ | "boxes are tight enough to steer by" |
| per-class | each > 0.3 | > 0.5 | a single dead class is a dataset bug |

Do not trust validation alone: **run it on the rover, in the actual room, with
`--dry-run`** and watch the command banner. The domain gap between a phone in
your hand and a phone 12 cm off the floor is real.

---

## 5. Deploy

```bash
unzip rover_yolo11n_bundle.zip -d models/
python scripts/ai_video_server.py --weights models/rover_yolo11n_openvino --dry-run
python scripts/ai_video_server.py --weights models/rover_yolo11n_openvino
```

Update `config/rover.json`:

```jsonc
"weights": "models/rover_yolo11n_openvino",
"zones": { "target_classes": [], "stop_area": 0.22, "speed": 150 }
```

Then re-tune `stop_area` on the floor: the fine-tuned boxes are tighter, so the
brake triggers at a different physical distance than with COCO weights.

---

## 5b. Bootstrap without rover images (COCO-6)

If you need a working 6-class model before you have rover frames, run the
bootstrap kernel:

```bash
make kaggle-coco6     # pushes kaggle/coco6
make kaggle-status
make kaggle-logs
```

It filters **COCO val2017** (attached as `awsaf49/coco-2017-dataset`) to
`person, chair, table, backpack, bottle, plant`, remaps the labels to the
rover's 6 classes, trains YOLO11n at 320 px, and exports OpenVINO + ONNX into
`rover6_bundle.zip`.

Measured result (80 epochs, 2,746 train / 485 val): **mAP50 0.267,
mAP50-95 0.161**, best classes person 0.325 and table 0.271. The bundle is
installed as `models/rover6_best.pt` and `config/rover.json` points at it.

Caveat: the train/val split comes from the same pool, so the reported mAP is
optimistic and the images are not from the rover's viewpoint. Treat it as a
**pipeline-validated bootstrap**, then re-run `kaggle/rover_finetune.ipynb` on
your own camera frames for the final model.

## 5c. Broader 24-class model + edge cases

The 6-class bootstrap proves the pipeline; the 24-class run is the model you
actually want on the rover today. It trains on **COCO train2017** (up to 12,000
images) and validates on **val2017** — the honest direction — and adds a stress
report.

Classes: person, bicycle, car, bench, cat, dog, backpack, handbag, suitcase,
bottle, cup, bowl, chair, couch, potted plant, bed, dining table, laptop,
cell phone, book, clock, vase, scissors, teddy bear.

```bash
make kaggle-coco24
make kaggle-status24
make kaggle-download24
python scripts/install_model.py /tmp/ai-rover-model/rover24_bundle.zip
```

Measured on 3,964 val2017 images: **mAP50 0.343, mAP50-95 0.225** (person 0.365,
cat 0.519, laptop 0.395, dining table 0.231, chair 0.121). The bundle includes
`edge_cases.json`: small objects drop to **0.173** (−17 points), clutter costs
0.039, dark/blur show no penalty on this sample. Methodology and how to act on
the numbers: [`docs/EDGE_CASES.md`](EDGE_CASES.md).

For arbitrary objects outside these 24 classes, use the open-vocabulary mode
(`--weights yolov8s-worldv2.pt --classes "door,cable,cone"`) — no retraining.

## 6. When to fine-tune vs. when to just use COCO

| Situation | Recommendation |
|---|---|
| Demo detects people, chairs, tables | stock `yolo11n.pt` is enough — no training |
| Rover must see doors, cables, ramps, cones | collect + fine-tune (those are not COCO classes) |
| COCO works but misses in your lighting | fine-tune on 200–300 rover frames |
| Laptop only manages 3 FPS | export OpenVINO before adding training complexity |

For the expo, a fine-tuned model with a clean `val_summary.json` is a stronger
story than "we used the default weights", but only if the numbers are honest.

---

## 7. Reproducibility (for the report)

Record in your report:

* dataset size, per-class counts, split ratio, seed
* base weights (`yolo11n.pt`, COCO)
* all hyperparameters (the notebook prints them in `args.yaml` under the run dir)
* mAP50 / mAP50-95 / per-class, and the confusion matrix image
* laptop CPU model + FPS for `.pt` vs OpenVINO
* the `data.yaml` used (it is inside the bundle)

All of it is written to `/kaggle/working` by the notebook; download the run
folder, not just `best.pt`.
