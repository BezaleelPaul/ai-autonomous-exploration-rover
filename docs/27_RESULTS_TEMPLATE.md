# 27. Experimental Results Template

**Document ID:** DOC-EXP-002
**Companion:** [`docs/26_EXPERIMENTAL_METHODOLOGY.md`](26_EXPERIMENTAL_METHODOLOGY.md) (protocols E01–E11)
**Purpose:** Consolidated record of *measured outcomes only*. Populate exclusively
from calibrated bench executions of the E01–E11 protocols. Never invent values.

---

## 1. Execution Log

| Field | Value |
|---|---|
| Date of campaign | `[YYYY-MM-DD]` |
| Operator(s) | `[NAME(S)]` |
| Rover HW revision | `[REV]` |
| Firmware git/commit ID | `[ID]` |
| Software config file used | `config/config.yaml` (`[HASH/DATE]`) |
| Instruments & calibration IDs | `[DMM/DSO/BENCH PSU IDs]` |
| Ambient temperature / humidity | `[ ] °C / [ ] %` |

---

## 2. Results Summary (one row per experiment)

| ID | Experiment | Trials | Key metric | Measured value (mean ± σ) | Units | Pass/Fail vs target | Deviation notes |
|---|---|---:|---|---|---|---|---|
| E01 | Motor Characterization & Speed Calibration | 5 | Speed @ 255 PWM | `[MEAN] ± [σ]` | m/s | `[P/F]` | |
| E02 | Ultrasonic Ranging Accuracy & Cone Angle | 5 | Mean abs. error @ 2 m | `[MEAN] ± [σ]` | cm | `[P/F]` | |
| E03 | Communication Latency & Watchdog Timing | 5 | Cmd-to-actuation latency | `[MEAN] ± [σ]` | ms | `[P/F]` | |
| E04 | Camera Frame Rate & Thermal Throttling | 5 | Sustained FPS | `[MEAN] ± [σ]` | fps | `[P/F]` | |
| E05 | Inference Latency per Backend | 5 | DETR/YOLO latency | `[MEAN] ± [σ]` | ms | `[P/F]` | |
| E06 | Target Acquisition & Tracking Accuracy | 5 | Acquire-to-lock time | `[MEAN] ± [σ]` | s | `[P/F]` | |
| E07 | Closed-Loop Approach Position Error | 5 | Final lateral error | `[MEAN] ± [σ]` | cm | `[P/F]` | |
| E08 | Emergency Stop Response Distance | 5 | Measured stop distance | `[MEAN] ± [σ]` | cm | `[P/F]` | must be < 15 cm threshold |
| E09 | Battery Runtime & Brownout Behavior | 5 | Runtime to cutoff | `[MEAN] ± [σ]` | min | `[P/F]` | |
| E10 | False-Positive / False-Negative Detection Rate | 5 | F1 score | `[MEAN] ± [σ]` | — | `[P/F]` | |
| E11 | End-to-End Navigation Success Rate | 5 | Success rate | `[MEAN] ± [σ]` | % | `[P/F]` | |

---

## 3. Per-Experiment Detail

For each experiment E01–E11, record:

- **Raw trial table** — copy the data rows from the corresponding protocol
  section of `26_EXPERIMENTAL_METHODOLOGY.md`, one column per trial T1–T5.
- **Derived statistics** — mean, sample standard deviation (n−1), min, max.
- **Acceptance criterion** — the pre-registered target from the protocol.
- **Verdict** — `PASS` only if the criterion is met by the measured values.
- **Anomalies** — any dropped trial, instrument glitch, or environmental
  disturbance, with justification for exclusion (never delete raw rows).

### Per-experiment block (duplicate for E01…E11)

```
Experiment: E[__] — [TITLE]
Date: [ ]   Operator: [ ]   Config: [ ]
+------+--------------+--------------+-----+
| Stat | Trial values | Mean | σ | Verdict |
+------+--------------+--------------+-----+
|  T1  | [ ]          |      |     |        |
|  T2  | [ ]          |      |     |        |
|  T3  | [ ]          |      |     |        |
|  T4  | [ ]          |      |     |        |
|  T5  | [ ]          | [  ] | [ ] | [P/F]  |
+------+--------------+--------------+-----+
Acceptance criterion: [ ]
Anomalies / exclusions: [ ]
```

---

## 4. Simulation vs Hardware Separation

Results obtained without powered hardware must be labelled **SIMULATED** and
kept in a separate section. Only rows backed by physical bench measurements
may appear in Section 2. Software-only evidence (pytest, firmware-host
harness, mocks) belongs in the CI report, not here.

---

## 5. Sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Test operator | | | |
| Reviewer | | | |
