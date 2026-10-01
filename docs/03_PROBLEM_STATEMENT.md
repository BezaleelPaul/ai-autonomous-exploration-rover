# 03. Problem Statement

## 1. Context and Problem Definition

Small-scale autonomous mobile robots frequently suffer from two engineering failure modes:
1. **The Tethering Fallacy:** Academic prototypes frequently claim "edge intelligence" while actually streaming video over local Wi-Fi to a high-powered desktop workstation executing heavy neural networks, which transmits motor commands back over radio. Such systems fail completely in field deployments where wireless latency, RF interference, and packet loss degrade control-loop stability.
2. **Monolithic Architecture Fragility:** In single-processor designs, CPU-intensive visual processing (such as image filtering or neural network tensor arithmetic) starves low-level PWM timing loops and sensor interrupt handlers. If a vision thread locks, the robot continues driving blindly into physical obstacles.

## 2. Technical Challenge

The technical challenge is to design an autonomous differential drive robotic vehicle that:
- Executes visual perception and decision logic locally on a low-cost microcontroller (ESP32).
- Maintains strict physical decoupling between high-level perception and low-level motor actuation.
- Ensures guaranteed hard real-time collision prevention and comms loss fail-stops using a dedicated hardware supervisor (Arduino UNO).
- Operates within an extreme power budget (< 20 W peak, < 5 W nominal) powered by a single 2S Li-ion battery pack.
