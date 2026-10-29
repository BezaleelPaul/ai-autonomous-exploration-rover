# 13. Decision Engine & Anti-Oscillation Logic

**Document ID:** DOC-NAV-001  
**Companion Diagram:** [`figures/06_decision_pipeline.png`](../figures/06_decision_pipeline.png)

## 1. Anti-Oscillation Deadband & State Latching

To prevent rapid chattering (limit cycles) when the target is near the zone boundary:
1. **Center Tolerance Deadband:** A tolerance window $\delta = \pm 0.06$ surrounds the optical center ($[0.44, 0.56]$). While the target error $|e| \le \delta$, the vehicle commands forward translation ('F').
2. **Minimum Command Duration:** Once a steering command ('L' or 'R') is issued, the state machine holds the command for $t_{min} = 0.40$ s before permitting state re-evaluation.
3. **Decision Cooldown:** A $0.20$ s refractory period prevents instantaneous switching on noisy single-frame misdetections.
4. **Proximity Termination:** When the bounding box width ratio reaches:
$$\frac{w_{bbox}}{W_{frame}} \ge 0.45$$
the rover infers that it has successfully arrived at the target ($~20$ cm standoff) and transitions to `STOPPED`.

![Decision Pipeline](../figures/06_decision_pipeline.png)

## 2. Implementation

The decision logic lives in the canonical control layer, not in a bespoke
engine module:

- **Zone -> command mapping** - `software/perception_node/zones.py`
  (`classify_zone`, `command_for_zone`) is the single source of truth, shared by
  the headless path and the Mission Deck's `SteeringPolicy`.
- **Position -> command + state** - `software/control/steering.py`
  (`command_for_position`).
- **Anti-oscillation** - `software/control/steering.py` (`AntiOscillation`);
  STOP is never delayed.
- **P-steering turn PWM** - `software/control/steering.py` (`p_steer_speed`),
  Protocol v2.
- **Finite search rotation** - `software/control/steering.py`
  (`SearchRotation`), timeout + capped rotations so it always terminates.

