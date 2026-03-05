#!/usr/bin/env python3
"""
NEXUS ARM Controller - Production Version
==========================================
Waypoint-based controller for NEXUS 6-DOF robot arm.

Hardware:
- PCA9685 PWM driver on Snarf (192.168.1.219)
- 5 servos: Base, Shoulder, Elbow, Wrist Yaw, Wrist Tilt
- Suction gripper (relay controlled)

Usage:
    from nexus_v2.hardware.arm_controller import NexusArm

    arm = NexusArm()
    arm.home()
    arm.pick_card(slot=1)
    arm.place_card(slot=5)
"""

import time
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict
import requests

logger = logging.getLogger(__name__)


@dataclass
class ServoConfig:
    """Configuration for a single servo"""
    channel: int          # PCA9685 channel (0-15)
    min_pulse: int        # Minimum pulse width (microseconds)
    max_pulse: int        # Maximum pulse width (microseconds)
    min_angle: float      # Minimum angle (degrees)
    max_angle: float      # Maximum angle (degrees)
    home_angle: float     # Home position angle
    inverted: bool = False  # Invert direction


@dataclass
class Waypoint:
    """A named position for the arm"""
    name: str
    angles: List[float]  # [base, shoulder, elbow, wrist_yaw, wrist_tilt]
    gripper: bool = False  # Gripper state at this waypoint


class NexusArm:
    """
    NEXUS 6-DOF Robot Arm Controller

    Uses pre-calibrated waypoints for reliable pick-and-place operations.
    Communicates with PCA9685 via Snarf's REST API.
    """

    # Hardware configuration
    SNARF_URL = "http://192.168.1.219:5001"

    # Servo configurations (calibrate these for your hardware)
    SERVOS = {
        'shoulder': ServoConfig(
            channel=1, min_pulse=500, max_pulse=2500,
            min_angle=-45, max_angle=90, home_angle=45, inverted=True
        ),
        'elbow': ServoConfig(
            channel=2, min_pulse=500, max_pulse=2500,
            min_angle=-120, max_angle=120, home_angle=60
        ),
        'wrist_yaw': ServoConfig(
            channel=3, min_pulse=500, max_pulse=2500,
            min_angle=-90, max_angle=90, home_angle=0
        ),
        'wrist_pitch': ServoConfig(
            channel=4, min_pulse=500, max_pulse=2500,
            min_angle=-90, max_angle=90, home_angle=-45
        ),
    }

    # Pre-calibrated waypoints (angles in degrees)
    # Calibrate these by manually positioning the arm and recording angles
    WAYPOINTS = {
        'home': Waypoint('home', [0, 45, 60, 0, -45]),
        'safe': Waypoint('safe', [0, 30, 30, 0, 0]),  # Safe travel position

        # Scanner pickup positions (cards come from CZUR scanner area)
        'scanner_above': Waypoint('scanner_above', [45, 60, 90, 0, -60]),
        'scanner_pick': Waypoint('scanner_pick', [45, 75, 110, 0, -90], gripper=True),

        # Sort bin positions (5 bins for sorting)
        'bin1_above': Waypoint('bin1_above', [-60, 50, 70, 0, -45]),
        'bin1_place': Waypoint('bin1_place', [-60, 65, 90, 0, -70]),
        'bin2_above': Waypoint('bin2_above', [-30, 50, 70, 0, -45]),
        'bin2_place': Waypoint('bin2_place', [-30, 65, 90, 0, -70]),
        'bin3_above': Waypoint('bin3_above', [0, 50, 70, 0, -45]),
        'bin3_place': Waypoint('bin3_place', [0, 65, 90, 0, -70]),
        'bin4_above': Waypoint('bin4_above', [30, 50, 70, 0, -45]),
        'bin4_place': Waypoint('bin4_place', [30, 65, 90, 0, -70]),
        'bin5_above': Waypoint('bin5_above', [60, 50, 70, 0, -45]),
        'bin5_place': Waypoint('bin5_place', [60, 65, 90, 0, -70]),
    }

    def __init__(self, snarf_url: str = None, simulation: bool = False):
        """
        Initialize arm controller.

        Args:
            snarf_url: Override default Snarf URL
            simulation: If True, don't send actual commands
        """
        self.snarf_url = snarf_url or self.SNARF_URL
        self.simulation = simulation
        self.current_angles = [0.0] * 5
        self.gripper_active = False
        self._connected = False

        logger.info(f"NexusArm initialized (simulation={simulation})")

    def connect(self) -> bool:
        """Test connection to Snarf"""
        if self.simulation:
            self._connected = True
            return True

        try:
            r = requests.get(f"{self.snarf_url}/api/arm/status", timeout=5)
            if r.status_code == 200:
                self._connected = True
                logger.info("Connected to arm controller")
                return True
        except Exception as e:
            logger.error(f"Failed to connect to Snarf: {e}")

        self._connected = False
        return False

    def _angle_to_pulse(self, servo: ServoConfig, angle: float) -> int:
        """Convert angle to PWM pulse width"""
        if servo.inverted:
            angle = -angle

        # Clamp to limits
        angle = max(servo.min_angle, min(servo.max_angle, angle))

        # Linear interpolation
        ratio = (angle - servo.min_angle) / (servo.max_angle - servo.min_angle)
        pulse = servo.min_pulse + ratio * (servo.max_pulse - servo.min_pulse)

        return int(pulse)

    def _send_joint_command(self, joint: int, angle: float) -> bool:
        """Send joint angle command via Snarf API"""
        if self.simulation:
            logger.debug(f"SIM: Joint {joint} -> {angle:.1f} deg")
            return True

        try:
            # Convert to 0-180 range for Snarf
            servo_angle = int(angle + 90)  # -90..90 -> 0..180
            servo_angle = max(0, min(180, servo_angle))

            r = requests.post(
                f"{self.snarf_url}/api/arm/set",
                json={'joint': joint, 'angle': servo_angle},
                timeout=2
            )
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Joint command failed: {e}")
            return False

    def _send_gripper_command(self, active: bool) -> bool:
        """Control suction gripper via relay"""
        if self.simulation:
            logger.debug(f"SIM: Gripper -> {'ON' if active else 'OFF'}")
            self.gripper_active = active
            return True

        try:
            r = requests.post(
                f"{self.snarf_url}/api/arm/gripper",
                json={'active': active},
                timeout=2
            )
            if r.status_code == 200:
                self.gripper_active = active
                return True
        except Exception as e:
            logger.error(f"Gripper command failed: {e}")
        return False

    def set_angles(self, angles: List[float], speed: float = 1.0):
        """
        Move all servos to specified angles.

        Args:
            angles: [base, shoulder, elbow, wrist_yaw, wrist_tilt] in degrees
            speed: Movement speed (0.1 = slow, 1.0 = fast)
        """
        if len(angles) != 5:
            raise ValueError("Expected 5 angles")

        # Calculate steps based on speed
        max_delta = max(abs(a - c) for a, c in zip(angles, self.current_angles))
        steps = max(1, int(max_delta / (5 * speed)))  # ~5 degrees per step at speed=1

        # Interpolate movement
        for step in range(steps):
            t = (step + 1) / steps
            # Smooth interpolation (ease in/out)
            t = t * t * (3 - 2 * t)

            for i in range(5):
                interp_angle = self.current_angles[i] + t * (angles[i] - self.current_angles[i])
                self._send_joint_command(i, interp_angle)

            time.sleep(0.02)  # 50Hz update rate

        self.current_angles = list(angles)

    def goto_waypoint(self, name: str, speed: float = 1.0) -> bool:
        """
        Move to a named waypoint.

        Args:
            name: Waypoint name
            speed: Movement speed

        Returns:
            True if successful
        """
        if name not in self.WAYPOINTS:
            logger.error(f"Unknown waypoint: {name}")
            return False

        waypoint = self.WAYPOINTS[name]
        logger.info(f"Moving to waypoint: {name}")

        self.set_angles(waypoint.angles, speed)

        if waypoint.gripper != self.gripper_active:
            self._send_gripper_command(waypoint.gripper)

        return True

    def home(self):
        """Move arm to home position"""
        logger.info("Moving to home position")
        self.gripper(False)
        self.goto_waypoint('safe', speed=0.5)
        self.goto_waypoint('home', speed=0.5)

    def gripper(self, active: bool):
        """Control gripper"""
        self._send_gripper_command(active)
        time.sleep(0.3 if active else 0.1)  # Wait for suction

    def pick_from_scanner(self) -> bool:
        """
        Pick up a card from the scanner area.

        Returns:
            True if pick was successful
        """
        logger.info("Picking card from scanner")

        # Move above scanner
        self.goto_waypoint('scanner_above')
        time.sleep(0.2)

        # Lower and grab
        self.goto_waypoint('scanner_pick', speed=0.5)
        self.gripper(True)
        time.sleep(0.3)

        # Lift
        self.goto_waypoint('scanner_above')

        # TODO: Add vacuum sensor check to verify pickup
        return True

    def place_in_bin(self, bin_number: int) -> bool:
        """
        Place card in specified bin (1-5).

        Args:
            bin_number: Bin number (1-5)

        Returns:
            True if successful
        """
        if not 1 <= bin_number <= 5:
            logger.error(f"Invalid bin number: {bin_number}")
            return False

        logger.info(f"Placing card in bin {bin_number}")

        # Move above bin
        self.goto_waypoint(f'bin{bin_number}_above')
        time.sleep(0.1)

        # Lower and release
        self.goto_waypoint(f'bin{bin_number}_place', speed=0.5)
        self.gripper(False)
        time.sleep(0.2)

        # Lift
        self.goto_waypoint(f'bin{bin_number}_above')

        return True

    def sort_card(self, bin_number: int) -> bool:
        """
        Complete sort cycle: pick from scanner, place in bin.

        Args:
            bin_number: Destination bin (1-5)

        Returns:
            True if successful
        """
        logger.info(f"Sorting card to bin {bin_number}")

        # Pick from scanner
        if not self.pick_from_scanner():
            logger.error("Failed to pick card")
            return False

        # Go to safe position for travel
        self.goto_waypoint('safe')

        # Place in bin
        if not self.place_in_bin(bin_number):
            logger.error("Failed to place card")
            return False

        # Return to safe position
        self.goto_waypoint('safe')

        logger.info("Sort complete")
        return True

    def calibrate_waypoint(self, name: str) -> List[float]:
        """
        Interactive waypoint calibration.
        Move arm manually, then call this to record current position.

        Args:
            name: Name for the waypoint

        Returns:
            Current angles
        """
        # In a real implementation, this would read actual servo positions
        # For now, return current commanded angles
        logger.info(f"Calibrated waypoint '{name}': {self.current_angles}")
        return self.current_angles.copy()

    def test_sequence(self):
        """Run a test sequence to verify arm operation"""
        logger.info("Running test sequence")

        print("=" * 50)
        print("NEXUS ARM TEST SEQUENCE")
        print("=" * 50)

        print("\n[1] Home position")
        self.home()
        time.sleep(1)

        print("\n[2] Scanner position")
        self.goto_waypoint('scanner_above')
        time.sleep(0.5)
        self.goto_waypoint('scanner_pick')
        time.sleep(0.5)

        print("\n[3] Gripper ON")
        self.gripper(True)
        time.sleep(0.5)

        print("\n[4] Lift")
        self.goto_waypoint('scanner_above')
        time.sleep(0.5)

        print("\n[5] Move to bin 3")
        self.goto_waypoint('safe')
        self.goto_waypoint('bin3_above')
        self.goto_waypoint('bin3_place')
        time.sleep(0.5)

        print("\n[6] Gripper OFF")
        self.gripper(False)
        time.sleep(0.5)

        print("\n[7] Return home")
        self.goto_waypoint('bin3_above')
        self.home()

        print("\n" + "=" * 50)
        print("TEST COMPLETE")
        print("=" * 50)


def main():
    """Test the arm controller"""
    logging.basicConfig(level=logging.INFO)

    # Run in simulation mode for testing
    arm = NexusArm(simulation=True)
    arm.connect()
    arm.test_sequence()


if __name__ == "__main__":
    main()
