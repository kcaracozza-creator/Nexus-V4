#!/usr/bin/env python3
"""
NEXUS Robot Arm Controller - Vision to Servo Bridge
====================================================
Takes card position from vision system, runs through trained
AI model, outputs servo commands to ESP32.

Flow: Camera → Vision → AI Model → Joint Angles → ESP32 → Servos

Patent Pending - Kevin Caracozza
"""

import os
import numpy as np
import time
import threading
import requests
from dataclasses import dataclass
from typing import Optional, Tuple, List
import json

# V3 imports
try:
    from light_control_v3 import LightControlV3
    LIGHTS_AVAILABLE = True
except ImportError:
    LIGHTS_AVAILABLE = False
    print("[ARM] Warning: light_control_v3 not available")

@dataclass
class ArmState:
    """Current arm state"""
    joints: List[float]  # [base, shoulder, elbow, wrist_roll, wrist_pitch] in degrees
    vacuum_on: bool
    holding_card: bool

@dataclass
class ArmCommand:
    """Command to send to arm"""
    joints: List[float]  # Target joint angles in degrees
    vacuum: bool         # Vacuum on/off
    speed: float = 1.0   # Movement speed multiplier

# Joint limits (degrees) - must match real hardware
JOINT_LIMITS = {
    0: (0, 180),    # Base
    1: (30, 150),   # Shoulder
    2: (30, 150),   # Elbow
    3: (0, 180),    # Wrist Roll
    4: (30, 150),   # Wrist Pitch
}

# Home position
HOME_POSITION = [90, 90, 90, 90, 90]

# Pickup position (arm down, ready to grab)
PICKUP_READY = [90, 60, 120, 90, 60]


class NexusArmController:
    """
    Controls the NEXUS robot arm using vision input and trained AI.
    """

    def __init__(self, esp32_url="http://192.168.1.172:5001", vision_url="http://192.168.1.172:5001"):
        self.esp32_url = esp32_url  # Snarf ESP32 for servo control
        self.vision_url = vision_url  # Vision system (also on Snarf)

        # Current state
        self.state = ArmState(
            joints=HOME_POSITION.copy(),
            vacuum_on=False,
            holding_card=False
        )

        # AI model (loaded from Zultan training)
        self.ai_model = None
        self.model_loaded = False

        # Light control V3 (ESP32 via USB)
        self.lights = None
        if LIGHTS_AVAILABLE:
            self.lights = LightControlV3()
            self.lights.connect()

        # Control thread
        self.running = False
        self.control_thread = None

        # Task queue
        self.task_queue = []
        self.current_task = None

        # Calibrated physical positions (overridden by load_calibration())
        self._cal_lightbox_x      = 50.0
        self._cal_lightbox_y      = 0.0
        self._cal_lightbox_joints = None
        self._cal_bin_x           = -150.0
        self._cal_bin_y           = 0.0
        self._cal_bin_joints      = None
        self._cal_scanner_joints  = None

    def load_model(self, model_path: str):
        """Load trained RL model from file"""
        try:
            from stable_baselines3 import PPO
            self.ai_model = PPO.load(model_path)
            self.model_loaded = True
            print(f"[ARM] Loaded AI model from {model_path}")
        except Exception as e:
            print(f"[ARM] Failed to load model: {e}")
            self.model_loaded = False

    def load_calibration(self, cal_path: str):
        """Load physical coordinate calibration from arm_calibration.json"""
        try:
            with open(cal_path) as f:
                cal = json.load(f)
            locs = cal.get("locations", {})
            if "LIGHTBOX" in locs:
                lb = locs["LIGHTBOX"]
                self._cal_lightbox_x = lb.get("approx_x_mm", 50)
                self._cal_lightbox_y = lb.get("approx_y_mm", 0)
                self._cal_lightbox_joints = lb.get("joints")
            if "SORT_BIN" in locs:
                sb = locs["SORT_BIN"]
                self._cal_bin_x = sb.get("approx_x_mm", -150)
                self._cal_bin_y = sb.get("approx_y_mm", 0)
                self._cal_bin_joints = sb.get("joints")
            if "SCANNER" in locs:
                sc = locs["SCANNER"]
                self._cal_scanner_joints = sc.get("joints")
            print(f"[ARM] Calibration loaded from {cal_path}")
            print(f"[ARM]   Lightbox XY  : ({self._cal_lightbox_x:+.0f}, {self._cal_lightbox_y:+.0f})mm")
            print(f"[ARM]   Sort bin XY  : ({self._cal_bin_x:+.0f}, {self._cal_bin_y:+.0f})mm")
        except FileNotFoundError:
            print(f"[ARM] No calibration file at {cal_path} — using defaults")
        except Exception as e:
            print(f"[ARM] Calibration load error: {e}")

    def start(self):
        """Start the arm controller"""
        self.running = True
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()
        print("[ARM] Controller started")

    def stop(self):
        """Stop the arm controller"""
        self.running = False
        if self.lights:
            self.lights.disconnect()
        self.go_home()

    def _control_loop(self):
        """Main control loop"""
        while self.running:
            # Process task queue
            if self.task_queue and self.current_task is None:
                self.current_task = self.task_queue.pop(0)
                self._execute_task(self.current_task)
                self.current_task = None

            time.sleep(0.05)

    def _execute_task(self, task: str):
        """Execute a task"""
        print(f"[ARM] Executing task: {task}")

        if task == "pick_card":
            self._task_pick_card()
        elif task == "place_card":
            self._task_place_card()
        elif task == "place_lightbox":
            self._task_place_lightbox()
        elif task == "pick_lightbox":
            self._task_pick_lightbox()
        elif task == "full_sort_cycle":
            self._task_full_sort_cycle()
        elif task == "home":
            self.go_home()
        elif task.startswith("move:"):
            # move:x,y,z
            coords = task.split(":")[1].split(",")
            x, y, z = float(coords[0]), float(coords[1]), float(coords[2])
            self.move_to_position(x, y, z)

    def _task_pick_card(self):
        """Pick up card using vision"""
        # Get card position from vision
        target = self.get_vision_target()
        if target is None:
            print("[ARM] No card detected")
            return False

        x_mm, y_mm, angle = target
        print(f"[ARM] Card at X={x_mm:.1f}mm Y={y_mm:.1f}mm Angle={angle:.1f}°")

        # Use AI model if loaded, otherwise use inverse kinematics
        if self.model_loaded and self.ai_model:
            joints = self._ai_calculate_joints(x_mm, y_mm, angle)
        else:
            joints = self._ik_calculate_joints(x_mm, y_mm, angle)

        # Move to above card
        joints_above = joints.copy()
        joints_above[1] += 20  # Raise shoulder
        joints_above[4] += 20  # Raise wrist
        self.move_joints(joints_above)
        time.sleep(0.5)

        # Move down to card
        self.move_joints(joints)
        time.sleep(0.3)

        # Activate vacuum
        self.set_vacuum(True)
        time.sleep(0.2)

        # Lift card
        self.move_joints(joints_above)
        time.sleep(0.3)

        self.state.holding_card = True
        print("[ARM] Card picked up")
        return True

    def _task_place_card(self, target_x=0, target_y=100):
        """Place card at target position"""
        if not self.state.holding_card:
            print("[ARM] Not holding a card")
            return False

        # Calculate joints for target position
        if self.model_loaded and self.ai_model:
            joints = self._ai_calculate_joints(target_x, target_y, 0)
        else:
            joints = self._ik_calculate_joints(target_x, target_y, 0)

        # Move to above target
        joints_above = joints.copy()
        joints_above[1] += 20
        joints_above[4] += 20
        self.move_joints(joints_above)
        time.sleep(0.5)

        # Move down
        self.move_joints(joints)
        time.sleep(0.3)

        # Release vacuum
        self.set_vacuum(False)
        time.sleep(0.2)

        # Lift arm
        self.move_joints(joints_above)
        time.sleep(0.3)

        self.state.holding_card = False
        print("[ARM] Card placed")
        return True

    def _task_place_lightbox(self, lightbox_x=None, lightbox_y=None):
        """Place card on light box for photography"""
        lightbox_x = lightbox_x if lightbox_x is not None else self._cal_lightbox_x
        lightbox_y = lightbox_y if lightbox_y is not None else self._cal_lightbox_y
        if not self.state.holding_card:
            print("[ARM] Not holding a card")
            return False

        print("[ARM] Placing card on light box for photo")

        # Calculate joints for light box position
        if self.model_loaded and self.ai_model:
            joints = self._ai_calculate_joints(lightbox_x, lightbox_y, 0)
        else:
            joints = self._ik_calculate_joints(lightbox_x, lightbox_y, 0)

        # Turn on lights BEFORE placing card
        if self.lights:
            self.lights.lights_on()
            time.sleep(0.2)

        # Move to above light box
        joints_above = joints.copy()
        joints_above[1] += 20
        joints_above[4] += 20
        self.move_joints(joints_above)
        time.sleep(0.5)

        # Move down gently (light box is delicate)
        self.move_joints(joints)
        time.sleep(0.3)

        # Release vacuum
        self.set_vacuum(False)
        time.sleep(0.2)

        # Lift arm
        self.move_joints(joints_above)
        time.sleep(0.3)

        self.state.holding_card = False
        print("[ARM] Card placed on light box (lights ON)")
        return True

    def _task_pick_lightbox(self, lightbox_x=None, lightbox_y=None):
        """Pick card from light box after photography"""
        lightbox_x = lightbox_x if lightbox_x is not None else self._cal_lightbox_x
        lightbox_y = lightbox_y if lightbox_y is not None else self._cal_lightbox_y
        if self.state.holding_card:
            print("[ARM] Already holding a card")
            return False

        print("[ARM] Picking card from light box")

        # Calculate joints for light box position
        if self.model_loaded and self.ai_model:
            joints = self._ai_calculate_joints(lightbox_x, lightbox_y, 0)
        else:
            joints = self._ik_calculate_joints(lightbox_x, lightbox_y, 0)

        # Move to above light box
        joints_above = joints.copy()
        joints_above[1] += 20
        joints_above[4] += 20
        self.move_joints(joints_above)
        time.sleep(0.5)

        # Move down to card
        self.move_joints(joints)
        time.sleep(0.3)

        # Activate vacuum
        self.set_vacuum(True)
        time.sleep(0.2)

        # Lift card
        self.move_joints(joints_above)
        time.sleep(0.3)

        # Turn off lights AFTER picking card
        if self.lights:
            self.lights.lights_off()

        self.state.holding_card = True
        print("[ARM] Card picked from light box (lights OFF)")
        return True

    def _task_full_sort_cycle(self, lightbox_x=None, lightbox_y=None, bin_x=None, bin_y=None):
        lightbox_x = lightbox_x if lightbox_x is not None else self._cal_lightbox_x
        lightbox_y = lightbox_y if lightbox_y is not None else self._cal_lightbox_y
        bin_x      = bin_x      if bin_x      is not None else self._cal_bin_x
        bin_y      = bin_y      if bin_y      is not None else self._cal_bin_y
        """
        Complete 3-location workflow:
        1. Pick card from scanner (using vision)
        2. Place on light box
        3. Wait for photo trigger
        4. Pick from light box
        5. Place in sort bin
        """
        print("[ARM] Starting full sort cycle")

        # Step 1: Pick from scanner
        if not self._task_pick_card():
            print("[ARM] Failed to pick card from scanner")
            return False
        time.sleep(0.5)

        # Step 2: Place on light box
        if not self._task_place_lightbox(lightbox_x, lightbox_y):
            print("[ARM] Failed to place on light box")
            return False
        time.sleep(0.5)

        # Step 3: Wait for photo (external trigger would go here)
        print("[ARM] Waiting for photo... (2 seconds)")
        time.sleep(2.0)

        # Step 4: Pick from light box
        if not self._task_pick_lightbox(lightbox_x, lightbox_y):
            print("[ARM] Failed to pick from light box")
            return False
        time.sleep(0.5)

        # Step 5: Place in bin
        if not self._task_place_card(bin_x, bin_y):
            print("[ARM] Failed to place in bin")
            return False

        print("[ARM] Full sort cycle complete!")
        return True

    def _ai_calculate_joints(self, x_mm: float, y_mm: float, angle: float) -> List[float]:
        """Use trained AI model to calculate joint angles"""
        # Normalize inputs for model (same as training)
        obs = np.array([
            x_mm / 150.0,   # Normalize to [-1, 1] assuming ±150mm workspace
            y_mm / 150.0,
            angle / 180.0,
            0.0, 0.0, 0.0,  # Placeholder for other obs (arm state)
            0.0, 0.0, 0.0,
            0.0, 0.0
        ], dtype=np.float32)

        # Get action from model
        action, _ = self.ai_model.predict(obs, deterministic=True)

        # Convert action to joint angles
        # Action is normalized [-1, 1], convert to degrees
        joints = []
        for i, act in enumerate(action[:5]):
            min_deg, max_deg = JOINT_LIMITS[i]
            # Map [-1, 1] to [min, max]
            joint_deg = (act + 1) / 2 * (max_deg - min_deg) + min_deg
            joints.append(joint_deg)

        return joints

    def _ik_calculate_joints(self, x_mm: float, y_mm: float, angle: float) -> List[float]:
        """Simple inverse kinematics fallback"""
        import math

        # Arm segment lengths (mm) - adjust to match real arm
        L1 = 80   # Base to shoulder
        L2 = 100  # Shoulder to elbow
        L3 = 100  # Elbow to wrist
        L4 = 50   # Wrist to tip

        # Calculate base rotation
        base_angle = math.degrees(math.atan2(y_mm, x_mm)) + 90
        base_angle = max(0, min(180, base_angle))

        # Distance in XY plane
        dist_xy = math.sqrt(x_mm**2 + y_mm**2)

        # Simple 2-link IK for shoulder and elbow
        # Assumes reaching down to table (z ≈ 0)
        reach = min(dist_xy, L2 + L3 - 20)  # Don't overextend

        # Elbow angle using law of cosines
        cos_elbow = (L2**2 + L3**2 - reach**2) / (2 * L2 * L3)
        cos_elbow = max(-1, min(1, cos_elbow))
        elbow_angle = 180 - math.degrees(math.acos(cos_elbow))
        elbow_angle = max(30, min(150, elbow_angle))

        # Shoulder angle
        shoulder_angle = 90 - math.degrees(math.atan2(reach, L1))
        shoulder_angle = max(30, min(150, shoulder_angle))

        # Wrist matches card angle
        wrist_roll = angle
        wrist_pitch = 90  # Pointing down

        return [base_angle, shoulder_angle, elbow_angle, wrist_roll, wrist_pitch]

    def get_vision_target(self) -> Optional[Tuple[float, float, float]]:
        """Get card position from vision system"""
        try:
            r = requests.get(f"{self.vision_url}/api/vision/arm_target", timeout=1)
            if r.status_code == 200:
                data = r.json()
                target = data.get('target')
                if target:
                    return (target['x'], target['y'], target['angle'])
        except Exception as e:
            print(f"[ARM] Vision error: {e}")
        return None

    def move_joints(self, joints: List[float]):
        """Send joint angles to ESP32"""
        # Clamp to limits
        clamped = []
        for i, angle in enumerate(joints):
            min_deg, max_deg = JOINT_LIMITS[i]
            clamped.append(max(min_deg, min(max_deg, angle)))

        try:
            r = requests.post(
                f"{self.esp32_url}/api/arm/move",
                json={'joints': clamped},
                timeout=2
            )
            if r.status_code == 200:
                self.state.joints = clamped
                return True
        except Exception as e:
            print(f"[ARM] Move error: {e}")
        return False

    def set_vacuum(self, on: bool):
        """Control vacuum gripper"""
        try:
            r = requests.post(
                f"{self.esp32_url}/api/arm/vacuum",
                json={'on': on},
                timeout=1
            )
            if r.status_code == 200:
                self.state.vacuum_on = on
                return True
        except Exception as e:
            print(f"[ARM] Vacuum error: {e}")
        return False

    def go_home(self):
        """Move to home position"""
        self.set_vacuum(False)
        self.move_joints(HOME_POSITION)
        self.state.holding_card = False

    def move_to_position(self, x_mm: float, y_mm: float, z_mm: float = 0):
        """Move to XYZ position"""
        joints = self._ik_calculate_joints(x_mm, y_mm, 0)
        self.move_joints(joints)

    def queue_task(self, task: str):
        """Add task to queue"""
        self.task_queue.append(task)

    def pick_and_place(self, target_x: float = 0, target_y: float = 100):
        """Pick up visible card and place at target"""
        self.queue_task("pick_card")
        self.queue_task(f"place:{target_x},{target_y}")


# =============================================================================
# API ENDPOINTS (add to Snarf server)
# =============================================================================

def create_arm_api(controller: NexusArmController):
    """Create Flask routes for arm control"""
    from flask import Flask, jsonify, request

    app = Flask(__name__)

    @app.route('/api/arm/status')
    def arm_status():
        return jsonify({
            'joints': controller.state.joints,
            'vacuum_on': controller.state.vacuum_on,
            'holding_card': controller.state.holding_card,
            'model_loaded': controller.model_loaded,
            'task_queue': len(controller.task_queue)
        })

    @app.route('/api/arm/home', methods=['POST'])
    def arm_home():
        controller.go_home()
        return jsonify({'status': 'ok'})

    @app.route('/api/arm/pick', methods=['POST'])
    def arm_pick():
        controller.queue_task("pick_card")
        return jsonify({'status': 'queued'})

    @app.route('/api/arm/place', methods=['POST'])
    def arm_place():
        data = request.json or {}
        x = data.get('x', 0)
        y = data.get('y', 100)
        controller.queue_task(f"place:{x},{y}")
        return jsonify({'status': 'queued'})

    @app.route('/api/arm/pick_and_place', methods=['POST'])
    def arm_pick_and_place():
        data = request.json or {}
        target_x = data.get('target_x', 0)
        target_y = data.get('target_y', 100)
        controller.pick_and_place(target_x, target_y)
        return jsonify({'status': 'queued'})

    @app.route('/api/arm/move', methods=['POST'])
    def arm_move():
        data = request.json
        joints = data.get('joints', HOME_POSITION)
        success = controller.move_joints(joints)
        return jsonify({'status': 'ok' if success else 'error'})

    @app.route('/api/arm/vacuum', methods=['POST'])
    def arm_vacuum():
        data = request.json
        on = data.get('on', False)
        success = controller.set_vacuum(on)
        return jsonify({'status': 'ok' if success else 'error'})

    return app


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == '__main__':
    print("[ARM] Starting arm controller test")

    controller = NexusArmController(
        esp32_url="http://192.168.1.218",       # ARM ESP32 direct IP
        vision_url="http://192.168.1.172:5001"  # Vision on SNARF
    )

    # Load calibration (generated by tools/arm_calibration.py)
    CAL_FILE = os.path.join(os.path.dirname(__file__), "arm_calibration.json")
    controller.load_calibration(CAL_FILE)

    # Load trained RL model (trained on ZULTAN, copied here)
    MODEL_FILE = os.path.join(os.path.dirname(__file__), "nexus_arm_final.zip")
    if os.path.exists(MODEL_FILE):
        controller.load_model(MODEL_FILE)
    else:
        print("[ARM] nexus_arm_final.zip not found — using IK fallback")
        print("[ARM] Copy from ZULTAN: scp zultan@192.168.1.152:~/training/nexus_arm_curriculum/nexus_arm_final.zip .")

    controller.start()

    try:
        print("\nCommands: pick, place, home, quit")
        while True:
            cmd = input("> ").strip().lower()
            if cmd == "quit":
                break
            elif cmd == "pick":
                controller.queue_task("pick_card")
            elif cmd == "place":
                controller.queue_task("place_card")
            elif cmd == "home":
                controller.go_home()
            elif cmd == "pp":
                controller.pick_and_place()
            else:
                print("Unknown command")
    finally:
        controller.stop()
