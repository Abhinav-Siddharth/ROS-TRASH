#!/usr/bin/env python3
"""Black-box acceptance check for the trash_boat mission. Do not edit thresholds."""

import argparse
import json
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.utilities import remove_ros_args
from std_msgs.msg import Int32


class Probe(Node):
    """Listen to the simulator's ground-truth status topics."""

    def __init__(self):
        super().__init__('acceptance_probe')
        self.collected = 0
        self.remaining = None
        self.bank_hits = 0
        self.create_subscription(Int32, 'trash_collected', self._on_collected, 10)
        self.create_subscription(Int32, 'trash_remaining', self._on_remaining, 10)
        self.create_subscription(Int32, 'bank_hits', self._on_bank_hits, 10)

    def _on_collected(self, msg):
        self.collected = msg.data

    def _on_remaining(self, msg):
        self.remaining = msg.data

    def _on_bank_hits(self, msg):
        self.bank_hits = msg.data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--total', type=int, default=12)
    parser.add_argument('--timeout', type=float, default=420.0)
    parser.add_argument('--min-ratio', type=float, default=0.9)
    parser.add_argument('--max-bank-hits', type=int, default=3)
    args = parser.parse_args(remove_ros_args(sys.argv)[1:])

    rclpy.init()
    probe = Probe()
    start = time.monotonic()
    while rclpy.ok() and time.monotonic() - start < args.timeout:
        rclpy.spin_once(probe, timeout_sec=0.2)
        if probe.remaining == 0:
            break
    # Let the final status messages arrive.
    settle_until = time.monotonic() + 1.5
    while time.monotonic() < settle_until:
        rclpy.spin_once(probe, timeout_sec=0.1)

    elapsed = time.monotonic() - start
    got_data = probe.remaining is not None
    ratio = probe.collected / args.total if args.total else 0.0
    ok = got_data and ratio >= args.min_ratio and probe.bank_hits <= args.max_bank_hits

    print(json.dumps({
        'passed': ok,
        'received_sim_data': got_data,
        'collected': probe.collected,
        'total': args.total,
        'ratio': round(ratio, 3),
        'bank_hits': probe.bank_hits,
        'wall_seconds': round(elapsed, 1),
    }))
    probe.destroy_node()
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
