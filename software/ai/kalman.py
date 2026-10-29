"""Constant-velocity Kalman filter over a detection box.

State: ``[cx, cy, w, h, vx, vy, vw, vh]`` — image-plane centre, size and their
velocities. Standard linear KF: ``predict(dt)`` advances the state (coasting
through missed detections), ``correct(z)`` folds a noisy measurement in.

Process noise uses the continuous white-noise acceleration (CWNA)
discretization — Q = q_a * [[dt^3/3, dt^2/2], [dt^2/2, dt]] per axis — which
couples position and velocity correctly; a naive (q*dt)^2 on position
explodes the innovation covariance and kills the velocity gain.

The posterior position variance P[0,0] + P[1,1] is the principled
uncertainty the world model turns into distance intervals — a track coasting
through an occlusion reports a much larger sigma than a freshly-corrected
one. ``size_rate`` (mean px/s growth of w/h) is the KF-grounded
"approaching" signal: an object moving toward the camera grows in the image
plane.
"""

from __future__ import annotations

import math

import numpy as np

# Measurement noise (px) on cx/cy/w/h.
DEFAULT_R = 12.0
# Continuous white-noise acceleration spectral density (px^2/s^3).
DEFAULT_Q_A = 800.0
DEFAULT_P_POS = 50.0
# Velocity is unobserved at t=0 — start maximally unsure so the first
# position innovations can actually move it (a small prior variance makes
# the position-to-velocity cross term negligible and the filter "sticks").
DEFAULT_P_VEL = 1.0e4


class BoxKalman:
    """8-state constant-velocity KF; measurements are (cx, cy, w, h)."""

    def __init__(
        self,
        z,
        *,
        r: float = DEFAULT_R,
        q_a: float = DEFAULT_Q_A,
        p_pos: float = DEFAULT_P_POS,
        p_vel: float = DEFAULT_P_VEL,
    ) -> None:
        cx, cy, w, h = (float(v) for v in z)
        self.x = np.array([cx, cy, w, h, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)
        self.P = np.diag([p_pos, p_pos, p_pos, p_pos, p_vel, p_vel, p_vel, p_vel])
        self.R = np.eye(4, dtype=np.float64) * (float(r) ** 2)
        self._q_a = float(q_a)
        self._last_innovation = np.zeros(4, dtype=np.float64)
        self._mahalanobis = 0.0

    def predict(self, dt: float) -> None:
        dt = max(1e-3, float(dt))
        f = np.eye(8, dtype=np.float64)
        f[0, 4] = dt
        f[1, 5] = dt
        f[2, 6] = dt
        f[3, 7] = dt
        # CWNA per (position, velocity) axis pair.
        q = np.zeros((8, 8), dtype=np.float64)
        q_pos = self._q_a * dt**3 / 3.0
        q_cross = self._q_a * dt**2 / 2.0
        q_vel = self._q_a * dt
        for i in range(4):
            q[i, i] = q_pos
            q[i, i + 4] = q_cross
            q[i + 4, i] = q_cross
            q[i + 4, i + 4] = q_vel
        self.x = f @ self.x
        self.P = f @ self.P @ f.T + q

    def correct(self, z) -> np.ndarray:
        z = np.asarray(tuple(float(v) for v in z), dtype=np.float64)
        h = np.zeros((4, 8), dtype=np.float64)
        h[:, :4] = np.eye(4)
        y = z - h @ self.x
        s = h @ self.P @ h.T + self.R
        k = self.P @ h.T @ np.linalg.inv(s)
        self.x = self.x + k @ y
        self.P = (np.eye(8) - k @ h) @ self.P
        self._last_innovation = y
        try:
            self._mahalanobis = float(
                math.sqrt(max(0.0, float(y @ np.linalg.solve(s, y))))
            )
        except np.linalg.LinAlgError:
            self._mahalanobis = 0.0
        return y

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (float(self.x[0]), float(self.x[1]), float(self.x[2]), float(self.x[3]))

    @property
    def pos_sigma_px(self) -> float:
        """Posterior sigma of the centre position, in pixels."""
        return float(math.sqrt(max(0.0, self.P[0, 0] + self.P[1, 1])))

    @property
    def size_rate(self) -> float:
        """Mean image-plane growth rate (px/s); positive = getting bigger."""
        return float((self.x[6] + self.x[7]) / 2.0)

    @property
    def speed_px(self) -> float:
        return float(math.hypot(self.x[4], self.x[5]))

    @property
    def mahalanobis(self) -> float:
        """Normalised last innovation — large values widen world-model sigmas."""
        return self._mahalanobis

    @property
    def last_innovation(self) -> np.ndarray:
        return self._last_innovation.copy()
