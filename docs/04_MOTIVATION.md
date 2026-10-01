# 04. Motivation & Justification

## 1. Engineering Motivation

1. **Edge Computing Feasibility:** Recent advances in TinyML (quantized neural networks, TensorFlow Lite for Microcontrollers, Edge Impulse FOMO) and embedded computer vision enable microcontrollers costing under $10 to perform perceptual tasks previously requiring industrial single-board computers.
2. **Defensive Robotics Architecture:** In critical robotic applications (warehouse AGVs, planetary rovers, inspection drones), the flight computer / high-level planner is never granted direct, unregulated control over physical motor lines. A hardware safety supervisor must always adjudicate commands.
3. **Cost-Effective Education and Research:** Demonstrating that reliable visual servoing and safety interlocks can be built with accessible commodity parts (ESP32-CAM, Arduino UNO, L298N) provides a high-value blueprint for undergraduate engineering curricula.
