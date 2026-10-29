# Copyright 2026 Abhinav Siddharth
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Pure safe-approach adaptation for a finite hull collecting shoreline trash."""

import math

from trash_boat_control.logic import CollectorLogic, Command


class MarineCollectorLogic:
    """Approach a safe water waypoint, then face the real visual target to scoop."""

    def __init__(self, reference: CollectorLogic, shore_clearance: float = 1.8,
                 end_clearance: float = 1.4, arrival_radius: float = 0.25,
                 alignment_distance: float = 1.1, dock_speed: float = 0.3,
                 dock_heading_tolerance: float = 0.15, dock_bank_margin: float = 1.1,
                 retreat_speed: float = 0.3, turn_in_place_threshold: float = 0.6) -> None:
        self.reference = reference
        self.shore_clearance = shore_clearance
        self.end_clearance = end_clearance
        self.arrival_radius = arrival_radius
        self.alignment_distance = alignment_distance
        self.dock_speed = dock_speed
        self.dock_heading_tolerance = dock_heading_tolerance
        self.dock_bank_margin = dock_bank_margin
        self.retreat_speed = retreat_speed
        self.turn_in_place_threshold = turn_in_place_threshold
        self.docking = False
        self.retreating = False
        if not (0 < shore_clearance < reference.half_width
                and 0 < end_clearance < reference.canal_length / 2
                and arrival_radius > 0 and alignment_distance > 0
                and 0 < dock_speed <= reference.approach_speed
                and 0 < retreat_speed <= reference.approach_speed
                and 0 < dock_heading_tolerance < math.pi / 2
                and 0 < dock_bank_margin < shore_clearance
                and 0 < turn_in_place_threshold <= reference.w_max):
            raise ValueError('Invalid marine approach geometry')

    def step(self, now: float, pose: tuple[float, float, float] | None,
             detections: list[tuple[float, float]], det_stamp: float | None) -> Command:
        """Preserve reference priorities and true-target scooping; adapt approach only."""
        reference = self.reference
        command = reference.step(now, pose, detections, det_stamp)
        if pose is None:
            return command
        x, y, yaw = pose
        safe_y = reference.half_width - self.shore_clearance
        outside = (abs(y) > safe_y or x < self.end_clearance
                   or x > reference.canal_length - self.end_clearance)
        if command.collect:
            self.retreating = outside
            self.docking = False
            return command
        if command.state == 'COLLECT':
            return command
        if self.retreating:
            if outside:
                return Command(v=-self.retreat_speed, w=0.0,
                               collect=False, state='APPROACH')
            self.retreating = False
        if command.state != 'APPROACH':
            if command.state == 'SEARCH' and abs(command.w) > self.turn_in_place_threshold:
                return Command(v=0.0, w=command.w, collect=False, state='SEARCH')
            if self.docking and command.state == 'SEARCH':
                return Command(v=0.0, w=0.0, collect=False, state='APPROACH')
            return command
        fwd, left = detections[0]
        cosine, sine = math.cos(yaw), math.sin(yaw)
        target_x = x + cosine * fwd - sine * left
        target_y = y + sine * fwd + cosine * left
        waypoint_x = max(self.end_clearance,
                         min(reference.canal_length - self.end_clearance, target_x))
        waypoint_y = max(-safe_y, min(safe_y, target_y))
        # Interior targets already use the proven direct visual approach.
        if not self.docking and waypoint_x == target_x and waypoint_y == target_y:
            return command
        dx, dy = waypoint_x - x, waypoint_y - y
        waypoint_distance = math.hypot(dx, dy)
        if (math.hypot(fwd, left) <= self.alignment_distance
                or waypoint_distance <= self.arrival_radius):
            self.docking = True
        if self.docking:
            bearing = math.atan2(left, fwd)
            speed = (self.dock_speed if abs(bearing) <= self.dock_heading_tolerance else 0.0)
            # Stop before a hull can cross a bank, even for an invalid visual target.
            outward = ((y > 0 and math.sin(yaw) > 0) or (y < 0 and math.sin(yaw) < 0))
            endward = ((x < self.dock_bank_margin and math.cos(yaw) < 0)
                       or (x > reference.canal_length - self.dock_bank_margin
                           and math.cos(yaw) > 0))
            if (outward and abs(y) >= reference.half_width - self.dock_bank_margin) or endward:
                speed = 0.0
        else:
            waypoint_fwd = cosine * dx + sine * dy
            waypoint_left = -sine * dx + cosine * dy
            bearing = math.atan2(waypoint_left, waypoint_fwd)
            speed = min(reference.approach_speed, reference.k_lin * waypoint_distance)
            speed *= max(0.0, math.cos(bearing))
        turn = max(-reference.w_max, min(reference.w_max, reference.k_ang * bearing))
        return Command(v=speed, w=turn, collect=False, state='APPROACH')
