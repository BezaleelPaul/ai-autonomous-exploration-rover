# 16. Arduino Motor Control & Actuation Firmware

**Document ID:** DOC-FW-001  
**Source Code:** [`arduino/rover_controller/rover_controller.ino`](../arduino/rover_controller/rover_controller.ino)

## 1. Firmware Design & Actuation Truth Table

The Arduino UNO firmware implements an event-driven loop operating without blocking delays (`delay()` is forbidden in the main loop). 

### H-Bridge Direction Control Truth Table:

| Command Char | Movement Action | ENA (Pin 5) | IN1 (Pin 6) | IN2 (Pin 7) | ENB (Pin 10) | IN3 (Pin 8) | IN4 (Pin 9) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `'F'` | Forward Translation | 200 PWM | HIGH | LOW | 200 PWM | HIGH | LOW |
| `'B'` | Reverse Translation | 200 PWM | LOW | HIGH | 200 PWM | LOW | HIGH |
| `'L'` | Pivot Spin Left | 200 PWM | LOW | HIGH | 200 PWM | HIGH | LOW |
| `'R'` | Pivot Spin Right | 200 PWM | HIGH | LOW | 200 PWM | LOW | HIGH |
| `'S'` | Active Motor Cutoff | 0 PWM | LOW | LOW | 0 PWM | LOW | LOW |
