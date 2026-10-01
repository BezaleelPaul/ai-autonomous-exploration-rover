# Edge cases handled

Perception: no object, low conf, false/missed detection, occlusion (largest-box
heuristic + lock timeout), multiples (largest wins), edge/small/large boxes.
Camera: disconnect, frozen frame (timeout -> safe STOP), corrupt JPEG, low/bright
light, blur (all -> no autonomous motion if require_camera_for_auto).
Navigation: obstacle ahead/left/right, dead end (STOP), target behind (360 scan
with rotation cap), target lost (reacquire timeout), unreachable (very-close STOP),
oscillation (min command duration + cooldown + center tolerance).
Gap: wide/medium/narrow, changing/moving (re-assess each cycle), uncertain ->
UNKNOWN which is never feasible. Comms: WiFi/serial fail, Arduino/ESP32 reboot,
process crash (Arduino comm-timeout stops motors independently). Power: brownout
-> Arduino reset -> comm timeout -> STOP. Invalid ultrasonic (-1/out of range) ->
block translation, allow turn; 5x invalid + forward -> STOP.
