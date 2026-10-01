# 33. Final Demonstration & Capstone Acceptance Protocol

**Document ID:** DOC-DEMO-001  

## 1. Acceptance Demonstration Procedure

1. **Stationary Pre-Flight Check:** Power rover on bench with wheels elevated. Verify 5.0V regulated logic rail and 7.4V motor rail.
2. **Autonomous Target Pursuit Demo:** Place target bottle 2.0 m ahead with slight lateral offset. Enable autonomous mode. Rover aligns to optical center and approaches until stopping cleanly at 20 cm standoff.
3. **Hardware Safety Barrier Demo:** During forward approach, introduce an obstacle 10 cm ahead of rover. Observe immediate hardware cutoff independently of visual tracking state.
4. **Loss-of-Signal Failsafe Demo:** Disconnect communication line during motion. Verify that motors halt within 3000 ms.
