#!/usr/bin/env python3
"""
NEXUS Robot Arm Simulation - PyBullet Environment
==================================================
Fast-track reinforcement learning for card manipulation tasks.

5-DOF Arm:
  Joint 0: Base (Z rotation)      - 0-180 degrees
  Joint 1: Shoulder (Y rotation)  - 30-150 degrees
  Joint 2: Elbow (Y rotation)     - 30-150 degrees
  Joint 3: WristRoll (X rotation) - 0-180 degrees
  Joint 4: WristPitch (Y rotation) - 30-150 degrees

Plus: Vacuum gripper (on/off)

Tasks:
  1. Card Pick: Move to card, activate vacuum, lift
  2. Card Place: Move to target, release vacuum
  3. Card Flip: Pick, rotate wrist 180, place
  4. Card Sort: Pick from pile, place in correct bin

Patent Pending - Kevin Caracozza
"""

import os
import numpy as np
import time
import math
from pathlib import Path
from collections import deque

# Pin to RTX 3060 explicitly — prevents falling back to iGPU or wrong device
# Change "0" to "1" if 3060 is the second CUDA device on your system
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

try:
    import pybullet as p
    import pybullet_data
    PYBULLET_AVAILABLE = True
except ImportError:
    PYBULLET_AVAILABLE = False
    print("PyBullet not installed. Run: pip install pybullet")

try:
    import gymnasium as gym
    from gymnasium import spaces
    GYM_AVAILABLE = True
except ImportError:
    try:
        import gym
        from gym import spaces
        GYM_AVAILABLE = True
    except ImportError:
        GYM_AVAILABLE = False
        print("Gymnasium not installed. Run: pip install gymnasium")


# Arm joint limits (degrees) - matches nexus_arm_robo_v3.urdf exactly
JOINT_LIMITS = {
    # Main arm (J0-J4) - from URDF limit tags, converted to degrees
    'base':         {'min': -180, 'max': 180, 'default':  0,  'channel': 0},
    'shoulder':     {'min':  -30, 'max':  90, 'default': 30,  'channel': 1},  # hardware constraint
    'elbow':        {'min': -114, 'max': 114, 'default':  0,  'channel': 2},
    'wrist_roll':   {'min': -180, 'max': 180, 'default':  0,  'channel': 3},
    'wrist_pitch':  {'min':  -90, 'max':  90, 'default':  0,  'channel': 4},
    # Lift mechanism (J5-J7) - unchanged
    'lift_tilt':    {'min': 0, 'max': 90,  'default': 45, 'channel': 5},
    'vacuum':       {'min': 0, 'max': 180, 'default':  0, 'channel': 6},
    'lift_shoulder':{'min': 0, 'max': 90,  'default': 45, 'channel': 7},
}

# Minimum gripper height above floor (meters) - prevents clipping through ground
MIN_GRIPPER_HEIGHT = 0.015  # 15mm - just above card thickness

NUM_ARM_JOINTS = 5      # Main arm
NUM_LIFT_JOINTS = 3     # Lift mechanism
NUM_TOTAL_JOINTS = 8    # All servos

# Convert to radians for simulation
def deg_to_rad(deg):
    return deg * math.pi / 180.0

def rad_to_deg(rad):
    return rad * 180.0 / math.pi


class NexusArmSim:
    """
    PyBullet simulation of 5-DOF NEXUS robot arm.
    Can run headless for fast training or with GUI for visualization.
    """

    def __init__(self, gui=False, time_step=1/240.0):
        if not PYBULLET_AVAILABLE:
            raise ImportError("PyBullet required. Install with: pip install pybullet")

        self.gui = gui
        self.time_step = time_step
        self.physics_client = None
        self.arm_id = None
        self.plane_id = None
        self.card_id = None
        self.lightbox_id = None  # Light box for photography
        self.target_id = None

        # Joint indices in URDF
        self.joint_indices = [0, 1, 2, 3, 4]  # 5-DOF

        # Vacuum cup state (no mechanical gripper - suction cup only)
        # pump_on=True + solenoid_open=False → holding suction
        # solenoid_open=True → pressure released → card drops
        self.pump_on = False
        self.solenoid_open = False
        self.gripped_object = None

        # Current joint angles (degrees) - safe home position matching URDF defaults
        self.joint_angles = [0, 30, 0, 0, 0]

        # Workspace boundaries (meters)
        self.workspace = {
            'x': (-0.3, 0.3),
            'y': (-0.3, 0.3),
            'z': (0.0, 0.25)
        }

        self._init_simulation()

    def _init_simulation(self):
        """Initialize PyBullet physics simulation"""
        if self.gui:
            self.physics_client = p.connect(p.GUI)
            p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
        else:
            self.physics_client = p.connect(p.DIRECT)

        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -9.81)
        p.setTimeStep(self.time_step)

        # Load ground plane
        self.plane_id = p.loadURDF("plane.urdf")

        # Load arm URDF
        urdf_path = Path(__file__).parent / "nexus_arm_robo_v3.urdf"
        if urdf_path.exists():
            self.arm_id = p.loadURDF(
                str(urdf_path),
                basePosition=[0, 0, 0],
                useFixedBase=True
            )
        else:
            # Create simple arm if URDF not found
            self._create_simple_arm()

        # Set initial joint positions
        self.reset_arm()

        # Create card object
        self._create_card()

        # Create light box zone (for photography)
        self._create_lightbox()

        # Create target zone (sort bin)
        self._create_target()

    def _create_simple_arm(self):
        """Create a simple multi-body arm if URDF fails"""
        # Base
        base_shape = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.04, height=0.02)
        base_visual = p.createVisualShape(p.GEOM_CYLINDER, radius=0.04, length=0.02,
                                          rgbaColor=[0.3, 0.3, 0.3, 1])

        self.arm_id = p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=base_shape,
            baseVisualShapeIndex=base_visual,
            basePosition=[0, 0, 0.01]
        )

    def _create_card(self, position=None):
        """Create a card object (trading card dimensions)"""
        # Standard card: 63mm x 88mm x 0.3mm
        card_size = [0.063, 0.088, 0.003]

        if position is None:
            position = [0.15, 0.0, 0.0015]  # On table in front of arm

        card_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=[s/2 for s in card_size])
        card_visual = p.createVisualShape(p.GEOM_BOX, halfExtents=[s/2 for s in card_size],
                                          rgbaColor=[1, 1, 1, 1])

        self.card_id = p.createMultiBody(
            baseMass=0.002,  # ~2 grams
            baseCollisionShapeIndex=card_shape,
            baseVisualShapeIndex=card_visual,
            basePosition=position
        )

        # Add card texture (optional)
        return self.card_id

    def _create_lightbox(self, position=None):
        """Create light box zone for photography (middle staging area)"""
        if position is None:
            # Position between scanner and bin - placeholder, will be calibrated
            position = [0.05, 0.0, 0.001]

        # Light box is slightly larger (100mm x 100mm)
        lightbox_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.05, 0.05, 0.001])
        lightbox_visual = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.05, 0.05, 0.001],
                                              rgbaColor=[1.0, 1.0, 0.3, 0.5])  # Yellow/amber

        self.lightbox_id = p.createMultiBody(
            baseMass=0,  # Static
            baseCollisionShapeIndex=lightbox_shape,
            baseVisualShapeIndex=lightbox_visual,
            basePosition=position
        )

    def _create_target(self, position=None):
        """Create target zone for final card placement (sort bin)"""
        if position is None:
            position = [-0.15, 0.0, 0.001]

        target_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.04, 0.05, 0.001])
        target_visual = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.04, 0.05, 0.001],
                                            rgbaColor=[0.2, 0.8, 0.2, 0.5])  # Green

        self.target_id = p.createMultiBody(
            baseMass=0,  # Static
            baseCollisionShapeIndex=target_shape,
            baseVisualShapeIndex=target_visual,
            basePosition=position
        )

    def reset_arm(self, angles=None):
        """Reset arm to default or specified position"""
        if angles is None:
            angles = [0, 30, 0, 0, 0]  # Safe home: base=0, shoulder=30, rest=0

        self.joint_angles = angles[:]

        if self.arm_id is not None:
            for i, angle in enumerate(angles):
                if i < p.getNumJoints(self.arm_id):
                    p.resetJointState(self.arm_id, i, deg_to_rad(angle))

        self.pump_on = False
        self.solenoid_open = False
        self.gripped_object = None

    def set_joint_angles(self, angles, speed=1.0):
        """
        Set target joint angles (degrees).
        Uses position control for smooth movement.
        """
        self.joint_angles = angles[:]

        if self.arm_id is None:
            return

        for i, angle in enumerate(angles):
            if i < p.getNumJoints(self.arm_id):
                p.setJointMotorControl2(
                    self.arm_id,
                    i,
                    p.POSITION_CONTROL,
                    targetPosition=deg_to_rad(angle),
                    maxVelocity=speed * 2.0,
                    force=10.0
                )

    def get_end_effector_pos(self):
        """Get current end effector position"""
        if self.arm_id is None:
            return [0, 0, 0]

        num_joints = p.getNumJoints(self.arm_id)
        if num_joints > 0:
            state = p.getLinkState(self.arm_id, num_joints - 1)
            return list(state[0])
        return [0, 0, 0]

    @property
    def gripper_active(self):
        """True when pump is running and solenoid is holding (suction engaged)"""
        return self.pump_on and not self.solenoid_open

    def set_vacuum(self, pump_on, solenoid_open):
        """
        Control vacuum cup hardware:
          pump_on=True, solenoid_open=False  → suction engaged (pick/hold card)
          solenoid_open=True                 → pressure released (drop card)
        Maps directly to ESP32 outputs: pump PWM + solenoid digital.
        """
        self.pump_on = pump_on
        self.solenoid_open = solenoid_open

        if self.gripper_active and self.card_id is not None:
            # Suction engaged - attach card if cup is touching it
            ee_pos = self.get_end_effector_pos()
            card_pos, card_orn = p.getBasePositionAndOrientation(self.card_id)
            distance = np.linalg.norm(np.array(ee_pos) - np.array(card_pos))

            # Cup must be within 2cm of card surface AND approaching from above
            above = ee_pos[2] >= card_pos[2]
            if distance < 0.02 and above and self.gripped_object is None:
                self.gripped_object = self.card_id
                self.grip_constraint = p.createConstraint(
                    self.arm_id,
                    p.getNumJoints(self.arm_id) - 1,
                    self.card_id,
                    -1,
                    p.JOINT_FIXED,
                    [0, 0, 0],
                    [0, 0, 0.01],
                    [0, 0, 0]
                )
        else:
            # Solenoid open or pump off — release
            if hasattr(self, 'grip_constraint'):
                p.removeConstraint(self.grip_constraint)
                del self.grip_constraint
            self.gripped_object = None

    def step(self, n_steps=1):
        """Step simulation forward"""
        for _ in range(n_steps):
            p.stepSimulation()
            if self.gui:
                time.sleep(self.time_step)

    def get_card_position(self):
        """Get current card position"""
        if self.card_id is None:
            return None
        pos, _ = p.getBasePositionAndOrientation(self.card_id)
        return list(pos)

    def get_lightbox_position(self):
        """Get light box position"""
        if self.lightbox_id is None:
            return None
        pos, _ = p.getBasePositionAndOrientation(self.lightbox_id)
        return list(pos)

    def get_target_position(self):
        """Get target zone position (sort bin)"""
        if self.target_id is None:
            return None
        pos, _ = p.getBasePositionAndOrientation(self.target_id)
        return list(pos)

    def is_card_at_target(self, threshold=0.03):
        """Check if card is at target position"""
        card_pos = self.get_card_position()
        target_pos = self.get_target_position()

        if card_pos is None or target_pos is None:
            return False

        distance = np.linalg.norm(
            np.array(card_pos[:2]) - np.array(target_pos[:2])
        )
        return distance < threshold

    def attach_card_to_gripper(self):
        """
        Force-attach card to end effector for curriculum Phase 3 reset.
        Bypasses distance check — card is teleported to EE then constrained.
        """
        if self.card_id is None or self.arm_id is None:
            return
        ee_pos = self.get_end_effector_pos()
        # Teleport card to just below end effector
        p.resetBasePositionAndOrientation(
            self.card_id,
            [ee_pos[0], ee_pos[1], max(0.005, ee_pos[2] - 0.01)],
            [0, 0, 0, 1]
        )
        p.stepSimulation()
        # Engage vacuum
        self.pump_on = True
        self.solenoid_open = False
        self.gripped_object = self.card_id
        self.grip_constraint = p.createConstraint(
            self.arm_id,
            p.getNumJoints(self.arm_id) - 1,
            self.card_id,
            -1,
            p.JOINT_FIXED,
            [0, 0, 0],
            [0, 0, 0.01],
            [0, 0, 0]
        )

    def reset_card(self, position=None):
        """Reset card to starting position"""
        if position is None:
            position = [0.15, 0.0, 0.0015]

        if self.card_id is not None:
            p.resetBasePositionAndOrientation(
                self.card_id,
                position,
                [0, 0, 0, 1]
            )

    def close(self):
        """Close simulation"""
        if self.physics_client is not None:
            p.disconnect(self.physics_client)
            self.physics_client = None


class NexusArmEnv(gym.Env):
    """
    Gymnasium environment for NEXUS arm reinforcement learning.

    Observation Space:
        - Joint angles (5 values, normalized 0-1)
        - End effector position (3 values)
        - Card position (3 values)
        - Light box position (3 values)
        - Target position (3 values)
        - Pump state (1 value: 0=off, 1=on)
        - Solenoid state (1 value: 0=closed/hold, 1=open/release)
        - Task stage (1 value: 0=pick, 1=to_lightbox, 2=from_lightbox, 3=to_bin)
        Total: 21 values

    Action Space:
        - Joint angle deltas (5 values, -1 to 1)
        - Pump command (1 value: >0.5=on, else off)
        - Solenoid command (1 value: >0.5=open/release, else closed/hold)
        Total: 7 values (continuous)

    Rewards:
        - Distance to card (when not gripping)
        - Distance to target (when gripping)
        - Bonus for successful placement
        - Penalty for dropping card
    """

    metadata = {'render_modes': ['human', 'rgb_array']}

    def __init__(self, render_mode=None, max_steps=500, curriculum_stage=0, physics_substeps=10):
        super().__init__()

        self.render_mode = render_mode
        self.max_steps = max_steps
        self.current_step = 0
        self.physics_substeps = physics_substeps  # substeps per env action

        # Curriculum stage:
        #   4 = Phase 0: gripper actuation only (200 steps, card under gripper)
        #   0 = Phase 1: pick from scanner + place on lightbox (stages 0-1)
        #   1 = Phase 2: pick back off lightbox (stage 2, card starts ON lightbox)
        #   2 = Phase 3: place in sort bin (stage 3, card starts in gripper)
        #   3 = Full run: all 4 stages end-to-end
        self.curriculum_stage = curriculum_stage

        # Create simulation
        gui = (render_mode == 'human')
        self.sim = NexusArmSim(gui=gui)

        # Define observation space (20D: 5 joints + 3 ee + 3 card + 3 lightbox + 3 bin + pump + solenoid + stage)
        self.observation_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(20,),
            dtype=np.float32
        )

        # Define action space (7D: 5 joints + pump + solenoid)
        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(7,),
            dtype=np.float32
        )

        # Task state (3-step workflow)
        self.has_card = False
        self.card_on_lightbox = False
        self.card_placed = False
        self.task_stage = 0  # 0=pick, 1=to_lightbox, 2=from_lightbox, 3=to_bin

    def _get_obs(self):
        """Get current observation"""
        # Normalize joint angles to 0-1
        joints_norm = []
        for i, angle in enumerate(self.sim.joint_angles):
            joint_name = list(JOINT_LIMITS.keys())[i]
            limits = JOINT_LIMITS[joint_name]
            norm = (angle - limits['min']) / (limits['max'] - limits['min'])
            joints_norm.append(np.clip(norm, 0, 1))

        # End effector position
        ee_pos = self.sim.get_end_effector_pos()

        # Card position
        card_pos = self.sim.get_card_position() or [0, 0, 0]

        # Light box position
        lightbox_pos = self.sim.get_lightbox_position() or [0, 0, 0]

        # Target position (sort bin)
        target_pos = self.sim.get_target_position() or [0, 0, 0]

        # Vacuum cup state (pump + solenoid separate)
        pump = 1.0 if self.sim.pump_on else 0.0
        solenoid = 1.0 if self.sim.solenoid_open else 0.0

        # Task stage (normalized 0-1)
        stage = self.task_stage / 3.0

        obs = np.array(
            joints_norm + ee_pos + card_pos + lightbox_pos + target_pos + [pump, solenoid, stage],
            dtype=np.float32
        )

        return obs

    def _get_reward(self):
        """
        Calculate reward for 3-step workflow:
        Stage 0: Pick card from scanner
        Stage 1: Place card on light box (for photo)
        Stage 2: Pick card from light box
        Stage 3: Place card in sort bin
        """
        reward = 0.0

        ee_pos = np.array(self.sim.get_end_effector_pos())
        card_pos = np.array(self.sim.get_card_position() or [0, 0, 0])
        lightbox_pos = np.array(self.sim.get_lightbox_position() or [0, 0, 0])
        target_pos = np.array(self.sim.get_target_position() or [0, 0, 0])

        # Phase 0 (curriculum 4): Vacuum cup actuation training only
        # Card is right under the EE - learn pump on + solenoid closed = suction
        if self.curriculum_stage == 4:
            dist_to_card = np.linalg.norm(ee_pos - card_pos)

            # Reward for being close to card
            reward += max(0, 0.5 - dist_to_card) * 2.0

            # Reward for pump on + solenoid closed (correct pick sequence) when close
            if self.sim.pump_on and not self.sim.solenoid_open and dist_to_card < 0.05:
                reward += 1.0

            # Penalize: pump on but solenoid open simultaneously (contradictory)
            if self.sim.pump_on and self.sim.solenoid_open:
                reward -= 1.0

            # Big bonus for actually gripping the card
            if self.sim.gripped_object is not None and not self.has_card:
                self.has_card = True
                reward += 50.0

            # Reward for releasing correctly (solenoid open when done)
            if self.has_card and self.sim.solenoid_open:
                reward += 5.0

            return reward  # Skip all other stage logic

        # Stage 0: Pick card from scanner
        if self.task_stage == 0:
            if not self.has_card:
                dist_to_card = np.linalg.norm(ee_pos - card_pos)
                reward -= dist_to_card * 1.0  # 10x stronger shaping
                # Partial credit for being close
                reward += max(0, 0.1 - dist_to_card) * 5.0

                if self.sim.gripped_object is not None:
                    self.has_card = True
                    self.task_stage = 1
                    reward += 50.0

        # Stage 1: Place card on light box
        elif self.task_stage == 1:
            dist_to_lightbox = np.linalg.norm(card_pos[:2] - lightbox_pos[:2])
            reward -= dist_to_lightbox * 1.0  # 10x stronger
            # Height guidance: reward lowering when over lightbox
            if dist_to_lightbox < 0.06:
                reward += max(0, 0.08 - ee_pos[2]) * 3.0

            if dist_to_lightbox < 0.03 and not self.sim.gripper_active:
                self.card_on_lightbox = True
                self.has_card = False
                self.task_stage = 2
                reward += 50.0

        # Stage 2: Pick card from light box
        elif self.task_stage == 2:
            if not self.has_card:
                dist_to_card = np.linalg.norm(ee_pos - card_pos)
                reward -= dist_to_card * 1.0  # 10x stronger
                reward += max(0, 0.1 - dist_to_card) * 5.0

                if self.sim.gripped_object is not None:
                    self.has_card = True
                    self.card_on_lightbox = False
                    self.task_stage = 3
                    reward += 50.0

        # Stage 3: Place card in sort bin
        elif self.task_stage == 3:
            dist_to_target = np.linalg.norm(card_pos[:2] - target_pos[:2])
            reward -= dist_to_target * 1.0  # 10x stronger
            # Height guidance: reward lowering when over bin
            if dist_to_target < 0.06:
                reward += max(0, 0.08 - ee_pos[2]) * 3.0
            # Partial credit for being close to bin
            reward += max(0, 0.1 - dist_to_target) * 5.0

            if self.sim.is_card_at_target() and not self.sim.gripper_active:
                self.card_placed = True
                reward += 100.0  # Success!

        # Small penalty per step to encourage efficiency
        reward -= 0.01

        # Floor constraint - heavy penalty if gripper goes below minimum height
        if ee_pos[2] < MIN_GRIPPER_HEIGHT:
            reward -= 20.0 * (MIN_GRIPPER_HEIGHT - ee_pos[2]) * 100

        return reward

    def step(self, action):
        """Execute action and return results"""
        self.current_step += 1

        # Parse action
        joint_deltas = action[:5] * 5.0  # Scale to degrees
        pump_cmd     = action[5] > 0.5   # >0.5 = pump on
        solenoid_cmd = action[6] > 0.5   # >0.5 = solenoid open (release)

        # Apply joint movements
        new_angles = []
        for i, (angle, delta) in enumerate(zip(self.sim.joint_angles, joint_deltas)):
            joint_name = list(JOINT_LIMITS.keys())[i]
            limits = JOINT_LIMITS[joint_name]
            new_angle = np.clip(angle + delta, limits['min'], limits['max'])
            new_angles.append(new_angle)

        self.sim.set_joint_angles(new_angles)

        # Control vacuum cup: pump + solenoid
        self.sim.set_vacuum(pump_on=pump_cmd, solenoid_open=solenoid_cmd)

        # Step simulation
        self.sim.step(n_steps=self.physics_substeps)

        # Get observation and reward
        obs = self._get_obs()
        reward = self._get_reward()

        # Check termination
        ee_z = self.sim.get_end_effector_pos()[2]
        floor_violation = ee_z < -0.005  # 5mm below floor = hard stop
        terminated = self.card_placed or floor_violation
        truncated = self.current_step >= self.max_steps

        info = {
            'has_card': self.has_card,
            'card_on_lightbox': self.card_on_lightbox,
            'card_placed': self.card_placed,
            'task_stage': self.task_stage,
            'steps': self.current_step,
            'floor_violation': floor_violation
        }

        return obs, reward, terminated, truncated, info

    def reset(self, seed=None, options=None):
        """Reset environment - starting state depends on curriculum_stage"""
        super().reset(seed=seed)
        if seed is not None:
            np.random.seed(seed)

        self.current_step = 0
        self.has_card = False
        self.card_on_lightbox = False
        self.card_placed = False
        self.sim.reset_arm()

        offset = np.random.uniform(-0.02, 0.02, size=2)

        if self.curriculum_stage == 4:
            # Phase 0: gripper actuation only
            # Card spawns directly below home-position end effector (~2cm drop)
            ee_home = self.sim.get_end_effector_pos()
            self.sim.reset_card([
                ee_home[0] + offset[0] * 0.5,  # tighter spread, card is close
                ee_home[1] + offset[1] * 0.5,
                max(0.0015, ee_home[2] - 0.025)  # 25mm below EE
            ])
            self.task_stage = 0

        elif self.curriculum_stage == 0:
            # Phase 1: card at scanner, arm at home, pick + place on lightbox
            self.task_stage = 0
            self.sim.reset_card([0.15 + offset[0], offset[1], 0.0015])

        elif self.curriculum_stage == 1:
            # Phase 2: card already ON lightbox, arm at home, pick back up
            lightbox_pos = self.sim.get_lightbox_position()
            self.sim.reset_card([
                lightbox_pos[0] + offset[0],
                lightbox_pos[1] + offset[1],
                0.0015
            ])
            self.card_on_lightbox = True
            self.task_stage = 2  # Start at stage 2 (pick from lightbox)

        elif self.curriculum_stage == 2:
            # Phase 3: card gripped, arm at home, place in sort bin
            # Must ACTUALLY attach card to gripper — not just set has_card flag
            self.sim.attach_card_to_gripper()
            self.has_card = True
            self.task_stage = 3  # Start at stage 3 (place in bin)

        else:
            # Full run: all 4 stages
            self.task_stage = 0
            self.sim.reset_card([0.15 + offset[0], offset[1], 0.0015])

        obs = self._get_obs()
        info = {'curriculum_stage': self.curriculum_stage}

        return obs, info

    def render(self):
        """Render environment"""
        if self.render_mode == 'human':
            pass  # GUI already showing
        elif self.render_mode == 'rgb_array':
            # Capture camera image
            width, height = 640, 480
            view_matrix = p.computeViewMatrix(
                cameraEyePosition=[0.5, 0.5, 0.3],
                cameraTargetPosition=[0, 0, 0.1],
                cameraUpVector=[0, 0, 1]
            )
            proj_matrix = p.computeProjectionMatrixFOV(
                fov=60, aspect=width/height, nearVal=0.1, farVal=100
            )
            _, _, rgb, _, _ = p.getCameraImage(
                width, height, view_matrix, proj_matrix
            )
            return np.array(rgb)[:, :, :3]

    def close(self):
        """Close environment"""
        self.sim.close()


# Training scripts

class SuccessRateCallback:
    """
    Tracks real task completion % across the last N episodes.
    Logs to TensorBoard as custom/success_rate_pct.
    """
    def __init__(self, window=100):
        self._successes = deque(maxlen=window)

    def _make_sb3_callback(self):
        """Returns an SB3-compatible BaseCallback wrapping this tracker."""
        try:
            from stable_baselines3.common.callbacks import BaseCallback

            outer = self

            class _CB(BaseCallback):
                def __init__(self):
                    super().__init__(verbose=0)

                def _on_step(self):
                    for info in self.locals.get('infos', []):
                        if 'episode' in info:  # end of episode
                            outer._successes.append(
                                1 if info.get('card_placed', False) else 0
                            )
                            if outer._successes:
                                rate = 100.0 * np.mean(outer._successes)
                                self.logger.record('custom/success_rate_pct', rate)
                    return True

            return _CB()
        except ImportError:
            return None


class EVThresholdCallback:
    """
    Saves a labeled checkpoint the first time explained_variance crosses a threshold.
    Useful for capturing 'phase solved' state without waiting for the full phase to end.

    Example:
        ev_saver = EVThresholdCallback(threshold=0.90, save_path="nexus_arm_curriculum", label="phase_2_ev90")
        model.learn(..., callback=CallbackList([..., ev_saver._make_sb3_callback(model)]))
    """
    def __init__(self, threshold=0.90, save_path="nexus_arm_curriculum", label="ev_threshold"):
        self.threshold = threshold
        self.save_path = save_path
        self.label = label
        self._triggered = False

    def _make_sb3_callback(self, model_ref):
        try:
            from stable_baselines3.common.callbacks import BaseCallback
            outer = self
            _model = model_ref

            class _CB(BaseCallback):
                def __init__(self):
                    super().__init__(verbose=0)

                def _on_step(self):
                    if outer._triggered:
                        return True
                    ev = self.logger.name_to_value.get('train/explained_variance', None)
                    if ev is not None and ev >= outer.threshold:
                        save_file = f"{outer.save_path}/{outer.label}"
                        _model.save(save_file)
                        print(f"\n  [EVThresholdCallback] EV={ev:.3f} >= {outer.threshold:.2f} — saved: {save_file}.zip")
                        outer._triggered = True
                    return True

            return _CB()
        except ImportError:
            return None

    def reset(self, label=None):
        """Call between phases to reuse with a new label."""
        self._triggered = False
        if label is not None:
            self.label = label


def _make_envs(curriculum_stage, n_envs=8, substeps=10):
    """Create parallel environments for a given curriculum stage"""
    from stable_baselines3.common.vec_env import SubprocVecEnv
    # Phase 0 (gripper) uses 200-step episodes; all others use 500
    max_steps = 200 if curriculum_stage == 4 else 500
    def make_env(rank):
        def _init():
            env = NexusArmEnv(curriculum_stage=curriculum_stage, max_steps=max_steps,
                              physics_substeps=substeps)
            return env
        return _init
    return SubprocVecEnv([make_env(i) for i in range(n_envs)])


def train_curriculum(timesteps_per_phase=200000, n_envs=16, save_dir="nexus_arm_curriculum"):
    """
    3-phase curriculum training for NEXUS scanner arm:
      Phase 1: Pick from scanner + place on lightbox (stages 0-1)
      Phase 2: Pick back off lightbox (stage 2)
      Phase 3: Place in sort bin (stage 3)
      Phase 4: Full end-to-end run (all 4 stages, fine-tune)
    """
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
    except ImportError:
        print("stable-baselines3 required. Run: pip install stable-baselines3")
        return None

    import os
    from datetime import datetime
    os.makedirs(save_dir, exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = f"{save_dir}/training_log_{run_id}.txt"

    def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        with open(log_path, 'a') as f:
            f.write(line + '\n')

    log(f"NEXUS Arm Curriculum Training - Run {run_id}")
    log(f"Save dir: {save_dir}")

    # Bigger network, cosine LR schedule, entropy bonus for exploration
    policy_kwargs = {'net_arch': [512, 512, 256]}

    def cosine_lr(progress_remaining):
        """Cosine decay from 3e-4 to 1e-5"""
        return 1e-5 + 0.5 * (3e-4 - 1e-5) * (1 + math.cos(math.pi * (1 - progress_remaining)))

    # Phase 3 (Sort Bin) gets 2x steps + 20 substeps for bin precision
    # substeps: phases 0-2 use 10 (fast), phase 3+ use 20 (precise)
    phases = [
        (4, "Phase 0 - Gripper Actuation (200-step episodes)", timesteps_per_phase // 2, 10),
        (0, "Phase 1 - Pick + Place on Lightbox",              timesteps_per_phase,       10),
        (1, "Phase 2 - Pick Back Off Lightbox",                timesteps_per_phase,       10),
        (2, "Phase 3 - Place in Sort Bin",                     timesteps_per_phase * 2,   20),
        (3, "Phase 4 - Full End-to-End (fine-tune)",           timesteps_per_phase,       20),
    ]

    tracker = SuccessRateCallback(window=100)
    ev_saver = EVThresholdCallback(threshold=0.90, save_path=save_dir)
    model = None

    for curriculum_stage, label, steps, substeps in phases:
        log(f"\n{'='*60}")
        log(f"  {label}")
        log(f"  {steps:,} timesteps  |  {n_envs} parallel envs  |  {substeps} substeps")
        log(f"{'='*60}")

        try:
            env = _make_envs(curriculum_stage, n_envs, substeps=substeps)
        except Exception:
            env = DummyVecEnv([lambda s=curriculum_stage: NexusArmEnv(curriculum_stage=s,
                                                                       physics_substeps=substeps)])

        if model is None:
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            print(f"  Device: {device}" + (f" ({torch.cuda.get_device_name(0)})" if device == 'cuda' else ''))
            model = PPO(
                "MlpPolicy",
                env,
                verbose=1,
                learning_rate=cosine_lr,
                n_steps=4096,          # deeper rollouts per update
                batch_size=512,
                n_epochs=10,
                gamma=0.995,
                ent_coef=0.01,         # entropy bonus: more exploration
                policy_kwargs=policy_kwargs,
                device=device,
                tensorboard_log=f"{save_dir}/tb/"
            )
        else:
            model.set_env(env)

        from stable_baselines3.common.callbacks import CheckpointCallback, CallbackList
        checkpoint_cb = CheckpointCallback(
            save_freq=100_000,
            save_path=f"{save_dir}/checkpoints/",
            name_prefix=f"stage{curriculum_stage}",
            verbose=1
        )
        success_cb = tracker._make_sb3_callback()
        ev_saver.reset(label=f"stage{curriculum_stage}_ev90")
        ev_cb = ev_saver._make_sb3_callback(model)
        cbs = [checkpoint_cb]
        if success_cb:
            cbs.append(success_cb)
        if ev_cb:
            cbs.append(ev_cb)
        callbacks = CallbackList(cbs)
        model.learn(total_timesteps=steps, reset_num_timesteps=False,
                    callback=callbacks)

        phase_save = f"{save_dir}/phase_{curriculum_stage}"
        model.save(phase_save)
        log(f"  Saved: {phase_save}.zip")
        env.close()

    final_save = f"{save_dir}/nexus_arm_final"
    model.save(final_save)
    log(f"Final model saved: {final_save}.zip")
    log(f"Training log: {log_path}")
    return model


def train_card_picker(total_timesteps=100000, save_path="nexus_arm_model"):
    """Single-phase training (no curriculum) - kept for quick tests"""
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv
    except ImportError:
        print("stable-baselines3 required. Run: pip install stable-baselines3")
        return None

    env = DummyVecEnv([lambda: NexusArmEnv()])
    model = PPO("MlpPolicy", env, verbose=1, learning_rate=3e-4,
                n_steps=2048, batch_size=64, n_epochs=10, gamma=0.99,
                device='cpu', tensorboard_log="./nexus_arm_tb/")
    print(f"Training for {total_timesteps} timesteps...")
    model.learn(total_timesteps=total_timesteps)
    model.save(save_path)
    print(f"Model saved to {save_path}")
    env.close()
    return model


def test_simulation():
    """Test simulation with manual control"""
    print("Testing NEXUS Arm Simulation...")

    sim = NexusArmSim(gui=True)

    print("Controls:")
    print("  Arm should be visible with card in front")
    print("  Simulation will run for 10 seconds")

    # Move arm in a pattern
    for i in range(500):
        angle = 90 + 30 * math.sin(i * 0.02)
        sim.set_joint_angles([90, angle, 90, 90, 90])
        sim.step(n_steps=4)

    sim.close()
    print("Test complete!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        timesteps = int(sys.argv[2]) if len(sys.argv) > 2 else 200000

        if cmd == "curriculum":
            # 3-phase curriculum: pick→lightbox→bin with weight transfer
            train_curriculum(timesteps_per_phase=timesteps)
        elif cmd == "train":
            # Quick single-phase training (no curriculum)
            train_card_picker(total_timesteps=timesteps)
        elif cmd == "test":
            test_simulation()
        else:
            print("Usage:")
            print("  python arm_sim.py curriculum [timesteps_per_phase]  - 3-phase curriculum (RECOMMENDED)")
            print("  python arm_sim.py train [timesteps]                 - Single-phase quick train")
            print("  python arm_sim.py test                              - Test with GUI")
    else:
        test_simulation()
