# Inference engine benchmark

Measured 2026-10-18 · random 640×480 frames · p50 = median latency · machine: i5-7300U (2C/4T), 8 GB, Intel HD Graphics 620 iGPU, no CUDA.

## Engines on CPU (yolo26n, Ultralytics predict path)

| engine | imgsz | p50 ms | FPS | notes |
|---|---:|---:|---:|---|
| torch | 320 | ~250 | ~4 | control baseline |
| onnx | 320 | 92 | 10.8 | default before iGPU work |
| onnx | 416 | 145 | 6.9 | previous default (small-object pick) |
| onnx | 640 | 249 | 4.0 | eats whole control budget |
| openvino (CPU) | 320 static | 41.3 | 24.2 | raw OpenVINO Runtime |
| openvino (CPU) | 416 static | 85.7 | 11.7 | raw OpenVINO Runtime |

## OpenVINO iGPU (Intel HD Graphics 620) — Ultralytics path

Static export, `device="intel:gpu"`:

| path | imgsz | p50 ms | FPS | vs onnx@416 (145 ms) |
|---|---:|---:|---:|---:|
| predict | 320 static | 50.7 | 19.7 | **2.9×** |
| track (ByteTrack) | 320 static | 66.9 | 14.9 | **2.2×** |
| track (ByteTrack) | 416 static | 180.8 | 5.5 | 0.8× (worse) |

**Dynamic shapes poison the iGPU:** `dynamic=True` @416 → 172 ms (shader recompilation per shape). Exports MUST be `dynamic=False`.

**416 on the iGPU is worse than 416 on CPU via ONNX** — the HD 620 chokes on the larger tensor plus Ultralytics wrapper overhead. The iGPU sweet spot is **static 320**.

## Wired detector (full `YoloDetector.detect` path, iGPU)

`ai.export: "openvino"`, `ai.openvino_device: "intel:gpu"`, `ai.yolo_imgsz: 320`:

- p50 **59.4 ms** (16.8 FPS) — includes ByteTrack + postprocess — **2.4× faster than the previous ONNX@416 default**.

## Winner

```yaml
ai.export: "openvino"
ai.openvino_device: "intel:gpu"   # auto-falls back to intel:cpu when no iGPU
ai.yolo_model: "yolo26n.pt"
ai.yolo_imgsz: 320                # MUST match the static export
```

Reproduce:

```bash
py -3.12 -c "from ultralytics import YOLO; YOLO('yolo26n.pt').export(format='openvino', imgsz=320, dynamic=False)"
```

Trade-off: 320 gives up some small-object recall vs 416 (see `config/config.yaml` `confidence_threshold` notes); at 17 FPS the control loop can afford a lower threshold or every-frame inference instead of every-Nth.
