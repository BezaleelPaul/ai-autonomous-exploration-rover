"""Tests for Local Bayesian Occupancy Grid and Costmap Navigation."""

from __future__ import annotations

import math
import numpy as np
import pytest

from software.navigation.occupancy_grid import CostmapConfig, LocalOccupancyGrid


def test_grid_world_roundtrip():
    cfg = CostmapConfig(width_m=4.0, height_m=4.0, resolution_m=0.05)
    grid = LocalOccupancyGrid(cfg)

    # Center is at (0, 0) in world coordinates
    assert grid.world_to_grid(0.0, 0.0) == (grid.origin_x, grid.origin_y)

    # Test coordinate round-trip
    wx, wy = 1.25, -0.75
    gx, gy = grid.world_to_grid(wx, wy)
    rx, ry = grid.grid_to_world(gx, gy)
    assert abs(wx - rx) <= cfg.resolution_m
    assert abs(wy - ry) <= cfg.resolution_m


def test_sonar_updates_free_and_occupied_cells():
    cfg = CostmapConfig(resolution_m=0.1)
    grid = LocalOccupancyGrid(cfg)

    # Ping obstacle at 1.0 m straight ahead
    grid.update_sonar_reading(distance_m=1.0)

    # Point at 0.5 m ahead should have decreased log-odds (free space)
    free_cell = grid.world_to_grid(0.5, 0.0)
    assert free_cell is not None
    assert grid.log_odds[free_cell[1], free_cell[0]] < 0.0

    # Point at 1.0 m ahead should have increased log-odds (occupied obstacle)
    occ_cell = grid.world_to_grid(1.0, 0.0)
    assert occ_cell is not None
    assert grid.log_odds[occ_cell[1], occ_cell[0]] > 0.0


def test_costmap_inflation():
    cfg = CostmapConfig(rover_radius_m=0.15, safety_margin_m=0.10, resolution_m=0.05)
    grid = LocalOccupancyGrid(cfg)

    # Add vision obstacle at 1.0 m ahead
    grid.add_vision_obstacle(1.0, 0.0, radius_m=0.05)
    costmap = grid.build_inflated_costmap()

    # The obstacle core should have high cost
    core_cell = grid.world_to_grid(1.0, 0.0)
    assert core_cell is not None
    assert costmap[core_cell[1], core_cell[0]] > 200

    # Neighbor within inflation zone should have positive cost
    neighbor_cell = grid.world_to_grid(0.85, 0.0)
    assert neighbor_cell is not None
    assert costmap[neighbor_cell[1], neighbor_cell[0]] > 0


def test_find_safe_heading_avoids_blocked_path():
    cfg = CostmapConfig(resolution_m=0.05)
    grid = LocalOccupancyGrid(cfg)

    # Place an obstacle directly ahead at 0.6 m
    grid.add_vision_obstacle(0.6, 0.0, radius_m=0.15)

    # Looking straight ahead (0 rad) should steer left or right to escape
    heading, is_safe = grid.find_safe_heading(target_heading_rad=0.0, lookahead_m=1.0)
    assert is_safe
    assert abs(heading) > 0.15  # Diverted away from straight center
