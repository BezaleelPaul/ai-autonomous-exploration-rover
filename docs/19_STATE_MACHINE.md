# 19. State Machine Implementation & Transition Matrix

**Document ID:** DOC-NAV-002  
**Companion Diagram:** [`figures/09_state_machine.png`](../figures/09_state_machine.png)

## 1. FSM Transition Matrix

| Current State | Event / Trigger | Guard Condition | Next State | Action Executed |
| :--- | :--- | :--- | :--- | :--- |
| **IDLE** | Mission Start | System Healthy | **SEARCHING** | Rotate slowly to acquire visual target |
| **SEARCHING**| Target Detected | Confidence $\ge 0.50$ | **ALIGNING** | Stop rotation, compute initial heading error |
| **SEARCHING**| Search Timeout | Time $> 30.0$ s or 2 turns | **STOPPED** | Cease search; signal mission timeout |
| **ALIGNING** | Target Centered | $|e| \le 0.06$ | **APPROACHING** | Command `'F'` (Drive straight) |
| **ALIGNING** | Target Off-Center | $|e| > 0.06$ | **ALIGNING** | Command `'L'` or `'R'` to reduce error |
| **APPROACHING**| Target Close | Bbox width ratio $\ge 0.45$ | **STOPPED** | Command `'S'`; mission objective complete |
| **APPROACHING**| Obstacle Detected| HC-SR04 $< 30.0$ cm | **AVOIDING** | Halt forward drive; initiate evasive turn |
| **ANY STATE** | Critical Obstacle| HC-SR04 $< 15.0$ cm | **EMERGENCY_STOP**| Hard motor cutoff; latch failsafe |
| **ANY STATE** | Comms Loss | No packet for $> 3000$ ms | **EMERGENCY_STOP**| Watchdog timeout; hard motor cutoff |
