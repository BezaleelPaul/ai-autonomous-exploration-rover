# Serial protocol v2 (9600 baud, newline-terminated)

PC -> Arduino: `F` forward, `B` back, `L` left, `R` right, `S` stop — each with
an optional PWM suffix `0..255` (e.g. `F180`, `L77`). No suffix = sticky
`activeSpeed` (boots at `rover.max_speed_pwm`). Digit bytes alone never refresh
the 3 s watchdog; overspeed (`>255`), mixed commands, or any unknown byte force
**STOP** + `STATUS:ERROR` (motors cleared, `currentCmd='S'`) — red-team H3.

Arduino -> PC every 200 ms: `DIST:<cm>` (float, -1 = invalid),
`STATUS:OK|STOP|ERROR`, `TICKS:<left>,<right>` (wheel-encoder ISR counts;
inert until encoders are fitted).

Safety on Arduino: blocks F/B if distance < 15cm; stops all on 3s comm timeout;
while driving F/B with encoders enabled, a per-wheel P velocity loop trims PWM
toward `config/config.yaml` `control:` targets and falls back to open loop
after silent encoder periods — see rover_controller.ino. Laptop SafetyManager
is the second layer and must also gate every command
(see software/safety/safety_manager.py).
