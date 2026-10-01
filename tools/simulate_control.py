"""Control theory simulation for differential drive rover vision-guided steering.

Simulates proportional steering: omega = Kp * e
where e = target_center_x - image_center_x (normalized).

NOTE: This is a mathematical simulation for tuning and control analysis.
DO NOT claim this simulation represents the real physical rover.
Explicitly labeled: SIMULATION — NOT MEASURED HARDWARE DATA.
"""

import os
import numpy as np
import matplotlib.pyplot as plt


def run_simulation(output_dir="figures"):
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs("docs/figures", exist_ok=True)

    dt = 0.05  # time step: 50 ms (20 Hz loop rate)
    t_total = 6.0  # total duration: 6 seconds
    time = np.arange(0, t_total, dt)

    # Initial condition: target detected at right edge of camera frame
    # Normalized coordinates: image center = 0.0, left = -0.5, right = +0.5
    initial_error = 0.40  # 40% offset from center

    # Physical vehicle parameters [ASSUMPTIONS based on 2WD chassis]
    # Rover track width L = 0.18 m, max angular velocity limit ~ 3.0 rad/s
    # Damping / steering lag modeled as 1st order lag: tau = 0.15 s
    tau = 0.15
    omega_max = 3.0  # saturation limit in rad/s

    kp_values = [0.2, 0.4, 0.6, 0.8, 1.2]
    colors = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd"]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True, dpi=300)

    for kp, col in zip(kp_values, colors):
        error = np.zeros_like(time)
        omega = np.zeros_like(time)
        e = initial_error
        w = 0.0

        for i, t in enumerate(time):
            # Proportional control command
            w_cmd = kp * e * 5.0  # scaling factor mapping normalized error to commanded yaw rate
            # Actuator saturation
            w_cmd = np.clip(w_cmd, -omega_max, omega_max)
            # 1st-order motor response lag: dw/dt = (w_cmd - w) / tau
            w += (w_cmd - w) * (dt / tau)
            # Kinematic error evolution: de/dt = - K_geom * w
            # where rotating the robot left decreases rightward target error
            de = - 0.45 * w * dt
            e += de

            error[i] = e
            omega[i] = w

        ax1.plot(time, error, label=f"Kp = {kp}", color=col, linewidth=2.0)
        ax2.plot(time, omega, label=f"Kp = {kp}", color=col, linewidth=2.0)

    # Plot 1: Target Error vs Time
    ax1.axhline(0, color="black", linestyle="--", linewidth=1.0, alpha=0.7)
    ax1.axhline(0.06, color="gray", linestyle=":", linewidth=1.0, label="Deadband (±0.06)")
    ax1.axhline(-0.06, color="gray", linestyle=":", linewidth=1.0)
    ax1.set_ylabel("Normalized Heading Error $e$ (norm)", fontsize=11, fontweight="bold")
    ax1.set_title("Proportional Steering Control Response Comparison\n"
                  "[SIMULATION — NOT MEASURED HARDWARE DATA]",
                  fontsize=13, fontweight="bold", pad=12, color="#b30000")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right", framealpha=0.9)
    ax1.set_ylim(-0.15, 0.45)

    # Plot 2: Commanded Angular Velocity vs Time
    ax2.axhline(0, color="black", linestyle="--", linewidth=1.0, alpha=0.7)
    ax2.set_xlabel("Time (seconds)", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Robot Angular Velocity $\\omega$ (rad/s)", fontsize=11, fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="upper right", framealpha=0.9)
    ax2.set_ylim(-0.5, 3.5)

    # Add watermark/disclaimer banner across bottom
    fig.text(0.5, 0.02,
             "CAUTION: SIMULATION DATA ONLY. PHYSICAL HARDWARE MEASUREMENTS REQUIRE EXPERIMENTAL ENCODER LOGGING.",
             ha="center", fontsize=9, fontweight="bold", color="#800000",
             bbox=dict(boxstyle="square,pad=0.3", fc="#fff3cd", ec="#ffeeba", lw=1))

    plt.tight_layout(rect=[0, 0.04, 1, 0.96])

    target_path = os.path.join(output_dir, "control_response_kp_comparison.png")
    fig.savefig(target_path, dpi=300)
    fig.savefig(os.path.join("docs/figures", "control_response_kp_comparison.png"), dpi=300)
    plt.close(fig)

    print(f"[OK] Control response simulation generated: {target_path}")
    return target_path


if __name__ == "__main__":
    run_simulation()
