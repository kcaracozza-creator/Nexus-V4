#!/usr/bin/env python3
"""
NEXUS Robot Arm Simulation - Stepper + Servo Hybrid
====================================================
Base (J0) and Shoulder (J1) = ZKSMC02 stepper drivers (CW/CCW) with 5:1 gearbox
Elbow, Wrist = Servos

Stepper characteristics:
  - Discrete step movement
  - NEMA17 + 5:1 gearbox = 16000 steps/rev at 16x microstep
  - ~44.44 steps/degree
  - Slower but more precise positioning

Patent Pending - Kevin Caracozza
"""

import numpy as np
import time
import math
from pathlib import Path

try:
    import pybullet as p
    import pybullet_data
    PYBULLET_AVAILABLE = True
except ImportError:
    PYBULLET_AVAILABLE = False

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:
    import gym
    from gym import spaces


# Joint configuration - STEPPER at base and shoulder (both 5:1 gearbox)
JOINT_CONFIG = {
    # Steppers (discrete movement) - 5:1 gearbox on both
    'base': {
        'type': 'stepper',
        'min': 0, 'max': 180, 'default': 90,
        'steps_per_deg': 44.44,  # NEMA17 + 5:1 gear + 16x microstep
        'max_speed': 800,  # steps/sec
        'gear_ratio': 5.0,
        'channel': 0, 'pins': [18, 19]
    },
    'shoulder': {
        'type': 'stepper',
        'min': 30, 'max': 150, 'default': 90,
        'steps_per_deg': 44.44,  # NEMA17 + 5:1 gear + 16x microstep
        'max_speed': 800,
        'gear_ratio': 5.0,
        'channel': 1, 'pins': [32, 33]
    },
    # Servos (continuous movement)
    'elbow': {
        'type': 'servo',
        'min': 30, 'max': 150, 'default': 90,
        'speed': 0.2,  # sec per 60 degrees
        'channel': 2
    },
    'wrist_roll': {
        'type': 'servo',
        'min': 0, 'max': 180, 'default': 90,
        'speed': 0.15,
        'channel': 3
    },
    'wrist_pitch': {
        'type': 'servo',
        'min': 30, 'max': 150, 'default': 90,
        'speed': 0.15,
        'channel': 4
    },
}

NUM_JOINTS = 5

def deg_to_rad(deg):
    return deg * math.pi / 180.0

def rad_to_deg(rad):
    return rad * 180.0 / math.pi


class StepperMotor:
    """Simulates stepper motor with gearbox"""

    def __init__(self, steps_per_deg=44.44, max_speed=800, gear_ratio=5.0):
        self.steps_per_deg = steps_per_deg
        self.max_speed = max_speed  # steps/sec
        self.gear_ratio = gear_ratio
        self.position_steps = 0
        self.target_steps = 0
        self.total_steps = 0  # Lifetime counter

    def set_angle(self, angle_deg):
        """Set target angle - converts to discrete steps"""
        self.target_steps = int(angle_deg * self.steps_per_deg)

    def get_angle(self):
        """Get current angle from step position"""
        return self.position_steps / self.steps_per_deg

    def update(self, dt):
        """Move toward target by stepping - returns True if still moving"""
        if self.position_steps == self.target_steps:
            return False

        # Calculate steps to move this tick
        max_steps = int(self.max_speed * dt)
        diff = self.target_steps - self.position_steps

        if abs(diff) <= max_steps:
            steps_moved = abs(diff)
            self.position_steps = self.target_steps
        else:
            steps_moved = max_steps
            self.position_steps += max_steps if diff > 0 else -max_steps

        self.total_steps += steps_moved
        return True

    def steps_remaining(self):
        """Steps left to reach target"""
        return abs(self.target_steps - self.position_steps)


class NexusArmSim:
    """PyBullet simulation with stepper + servo hybrid"""

    def __init__(self, gui=False, time_step=1/240.0):
        if not PYBULLET_AVAILABLE:
            raise ImportError("PyBullet required")

        self.gui = gui
        self.time_step = time_step
        self.physics_client = None
        self.arm_id = None
        self.plane_id = None
        self.card_id = None
        self.target_id = None

        self.joint_indices = list(range(NUM_JOINTS))
        self.gripper_active = False
        self.gripped_object = None

        # Current joint angles (degrees)
        self.joint_angles = [90, 90, 90, 90, 90]

        # Stepper motors for J0 and J1 (both with 5:1 gearbox)
        self.steppers = {
            0: StepperMotor(
                steps_per_deg=JOINT_CONFIG['base']['steps_per_deg'],
                max_speed=JOINT_CONFIG['base']['max_speed'],
                gear_ratio=JOINT_CONFIG['base']['gear_ratio']
            ),
            1: StepperMotor(
                steps_per_deg=JOINT_CONFIG['shoulder']['steps_per_deg'],
                max_speed=JOINT_CONFIG['shoulder']['max_speed'],
                gear_ratio=JOINT_CONFIG['shoulder']['gear_ratio']
            ),
        }

        # Initialize steppers to default position
        for idx, stepper in self.steppers.items():
            stepper.set_angle(90)
            stepper.position_steps = stepper.target_steps

        self.workspace = {
            'x': (-0.3, 0.3),
            'y': (-0.3, 0.3),
            'z': (0.0, 0.25)
        }

        self._init_simulation()

    def _init_simulation(self):
        if self.gui:
            self.physics_client = p.connect(p.GUI)
            p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
        else:
            self.physics_client = p.connect(p.DIRECT)

        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -9.81)
        p.setTimeStep(self.time_step)

        self.plane_id = p.loadURDF("plane.urdf")

        urdf_path = Path(__file__).parent / "nexus_arm.urdf"
        if urdf_path.exists():
            self.arm_id = p.loadURDF(str(urdf_path), basePosition=[0, 0, 0], useFixedBase=True)
        else:
            self._create_simple_arm()

        self.reset_arm()
        self._create_card()
        self._create_target()

    def _create_simple_arm(self):
        base_shape = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.04, height=0.02)
        base_visual = p.createVisualShape(p.GEOM_CYLINDER, radius=0.04, length=0.02, rgbaColor=[0.3, 0.3, 0.3, 1])
        self.arm_id = p.createMultiBody(baseMass=0, baseCollisionShapeIndex=base_shape,
                                        baseVisualShapeIndex=base_visual, basePosition=[0, 0, 0.01])

    def _create_card(self, position=None):
        card_size = [0.063, 0.088, 0.003]
        if position is None:
            position = [0.15, 0.0, 0.0015]
        card_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=[s/2 for s in card_size])
        card_visual = p.createVisualShape(p.GEOM_BOX, halfExtents=[s/2 for s in card_size], rgbaColor=[1, 1, 1, 1])
        self.card_id = p.createMultiBody(baseMass=0.002, baseCollisionShapeIndex=card_shape,
                                         baseVisualShapeIndex=card_visual, basePosition=position)

    def _create_target(self, position=None):
        if position is None:
            position = [-0.15, 0.0, 0.001]
        target_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.04, 0.05, 0.001])
        target_visual = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.04, 0.05, 0.001], rgbaColor=[0.2, 0.8, 0.2, 0.5])
        self.target_id = p.createMultiBody(baseMass=0, baseCollisionShapeIndex=target_shape,
                                           baseVisualShapeIndex=target_visual, basePosition=position)

    def reset_arm(self, angles=None):
        if angles is None:
            angles = [90, 90, 90, 90, 90]
        self.joint_angles = angles[:]

        # Reset steppers
        for idx, stepper in self.steppers.items():
            stepper.set_angle(angles[idx])
            stepper.position_steps = stepper.target_steps
            stepper.total_steps = 0

        if self.arm_id is not None:
            for i, angle in enumerate(angles):
                if i < p.getNumJoints(self.arm_id):
                    p.resetJointState(self.arm_id, i, deg_to_rad(angle))

        self.gripper_active = False
        self.gripped_object = None

    def set_joint_angles(self, angles, speed=1.0):
        """Set target joint angles - steppers move discretely, servos continuously"""

        for i, angle in enumerate(angles):
            joint_name = list(JOINT_CONFIG.keys())[i]
            limits = JOINT_CONFIG[joint_name]
            angle = np.clip(angle, limits['min'], limits['max'])

            if i in self.steppers:
                # Stepper: set target (discrete movement happens in step())
                self.steppers[i].set_angle(angle)
            else:
                # Servo: continuous position control
                self.joint_angles[i] = angle
                if self.arm_id is not None and i < p.getNumJoints(self.arm_id):
                    p.setJointMotorControl2(
                        self.arm_id, i, p.POSITION_CONTROL,
                        targetPosition=deg_to_rad(angle),
                        maxVelocity=speed * 2.0, force=10.0
                    )

    def step(self, n_steps=1):
        """Step simulation - includes stepper motor updates"""
        dt = self.time_step * n_steps

        # Update stepper motors
        for idx, stepper in self.steppers.items():
            stepper.update(dt)
            self.joint_angles[idx] = stepper.get_angle()

            # Apply to physics
            if self.arm_id is not None and idx < p.getNumJoints(self.arm_id):
                p.resetJointState(self.arm_id, idx, deg_to_rad(self.joint_angles[idx]))

        for _ in range(n_steps):
            p.stepSimulation()
            if self.gui:
                time.sleep(self.time_step)

    def get_end_effector_pos(self):
        if self.arm_id is None:
            return [0, 0, 0]
        num_joints = p.getNumJoints(self.arm_id)
        if num_joints > 0:
            state = p.getLinkState(self.arm_id, num_joints - 1)
            return list(state[0])
        return [0, 0, 0]

    def activate_gripper(self, active=True):
        self.gripper_active = active
        if active and self.card_id is not None:
            ee_pos = self.get_end_effector_pos()
            card_pos, _ = p.getBasePositionAndOrientation(self.card_id)
            distance = np.linalg.norm(np.array(ee_pos) - np.array(card_pos))
            if distance < 0.03:
                self.gripped_object = self.card_id
                self.grip_constraint = p.createConstraint(
                    self.arm_id, p.getNumJoints(self.arm_id) - 1, self.card_id, -1,
                    p.JOINT_FIXED, [0, 0, 0], [0, 0, 0.02], [0, 0, 0]
                )
        else:
            if hasattr(self, 'grip_constraint'):
                p.removeConstraint(self.grip_constraint)
                del self.grip_constraint
            self.gripped_object = None

    def get_card_position(self):
        if self.card_id is None:
            return None
        pos, _ = p.getBasePositionAndOrientation(self.card_id)
        return list(pos)

    def get_target_position(self):
        if self.target_id is None:
            return None
        pos, _ = p.getBasePositionAndOrientation(self.target_id)
        return list(pos)

    def is_card_at_target(self, threshold=0.03):
        card_pos = self.get_card_position()
        target_pos = self.get_target_position()
        if card_pos is None or target_pos is None:
            return False
        distance = np.linalg.norm(np.array(card_pos[:2]) - np.array(target_pos[:2]))
        return distance < threshold

    def reset_card(self, position=None):
        if position is None:
            position = [0.15, 0.0, 0.0015]
        if self.card_id is not None:
            p.resetBasePositionAndOrientation(self.card_id, position, [0, 0, 0, 1])

    def get_stepper_stats(self):
        """Get stepper motor statistics"""
        return {
            'base': {
                'angle': self.steppers[0].get_angle(),
                'target': self.steppers[0].target_steps / self.steppers[0].steps_per_deg,
                'remaining': self.steppers[0].steps_remaining(),
                'total_steps': self.steppers[0].total_steps
            },
            'shoulder': {
                'angle': self.steppers[1].get_angle(),
                'target': self.steppers[1].target_steps / self.steppers[1].steps_per_deg,
                'remaining': self.steppers[1].steps_remaining(),
                'total_steps': self.steppers[1].total_steps
            }
        }

    def close(self):
        if self.physics_client is not None:
            p.disconnect(self.physics_client)
            self.physics_client = None


class NexusArmEnv(gym.Env):
    """Gym environment for stepper+servo hybrid arm"""

    metadata = {'render_modes': ['human', 'rgb_array']}

    def __init__(self, render_mode=None, max_steps=200):
        super().__init__()
        self.render_mode = render_mode
        self.max_steps = max_steps
        self.current_step = 0

        gui = (render_mode == 'human')
        self.sim = NexusArmSim(gui=gui)

        # Observation: joints(5) + ee_pos(3) + card_pos(3) + target_pos(3) + gripper(1) + stepper_moving(2)
        self.observation_space = spaces.Box(low=-1.0, high=1.0, shape=(17,), dtype=np.float32)

        # Action: joint deltas(5) + gripper(1)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32)

        self.has_card = False
        self.card_placed = False

    def _get_obs(self):
        joints_norm = []
        for i, angle in enumerate(self.sim.joint_angles):
            joint_name = list(JOINT_CONFIG.keys())[i]
            limits = JOINT_CONFIG[joint_name]
            norm = (angle - limits['min']) / (limits['max'] - limits['min'])
            joints_norm.append(np.clip(norm * 2 - 1, -1, 1))  # Normalize to -1,1

        ee_pos = self.sim.get_end_effector_pos()
        card_pos = self.sim.get_card_position() or [0, 0, 0]
        target_pos = self.sim.get_target_position() or [0, 0, 0]
        gripper = 1.0 if self.sim.gripper_active else -1.0

        # Stepper status (are they still moving?)
        stepper_moving = [
            1.0 if self.sim.steppers[0].position_steps != self.sim.steppers[0].target_steps else -1.0,
            1.0 if self.sim.steppers[1].position_steps != self.sim.steppers[1].target_steps else -1.0,
        ]

        obs = np.array(joints_norm + ee_pos + card_pos + target_pos + [gripper] + stepper_moving, dtype=np.float32)
        return obs

    def _get_reward(self):
        ee_pos = np.array(self.sim.get_end_effector_pos())
        card_pos = np.array(self.sim.get_card_position() or [0, 0, 0])
        target_pos = np.array(self.sim.get_target_position() or [0, 0, 0])
        
        if not self.has_card:
            dist = np.linalg.norm(ee_pos - card_pos)
            max_dist = 0.4
            reward = (1.0 - dist / max_dist) * 2.0
            
            if dist < 0.05:
                reward += 5.0
            if dist < 0.03:
                reward += 10.0
                
            if self.sim.gripped_object is not None:
                self.has_card = True
                reward += 100.0
        else:
            dist = np.linalg.norm(card_pos[:2] - target_pos[:2])
            max_dist = 0.4
            
            reward = (1.0 - dist / max_dist) * 2.0 + 5.0
            
            if dist < 0.05:
                reward += 10.0
            if dist < 0.03:
                reward += 20.0
                
            if self.sim.is_card_at_target() and not self.sim.gripper_active:
                self.card_placed = True
                reward += 200.0
        
        reward -= 0.001
        return reward
    def step(self, action):
        self.current_step += 1

        # Steppers move slower - scale action differently
        joint_deltas = []
        for i in range(5):
            if i in self.sim.steppers:
                # Steppers: smaller deltas (they're slower due to gearbox)
                joint_deltas.append(action[i] * 2.0)
            else:
                # Servos: normal deltas
                joint_deltas.append(action[i] * 5.0)

        gripper_action = action[5]

        new_angles = []
        for i, (angle, delta) in enumerate(zip(self.sim.joint_angles, joint_deltas)):
            joint_name = list(JOINT_CONFIG.keys())[i]
            limits = JOINT_CONFIG[joint_name]
            new_angle = np.clip(angle + delta, limits['min'], limits['max'])
            new_angles.append(new_angle)

        self.sim.set_joint_angles(new_angles)

        if gripper_action > 0.5:
            self.sim.activate_gripper(True)
        elif gripper_action < -0.5:
            self.sim.activate_gripper(False)

        self.sim.step(n_steps=2)

        obs = self._get_obs()
        reward = self._get_reward()
        terminated = self.card_placed
        truncated = self.current_step >= self.max_steps

        info = {'has_card': self.has_card, 'card_placed': self.card_placed, 'steps': self.current_step}
        return obs, reward, terminated, truncated, info

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.has_card = False
        self.card_placed = False

        self.sim.reset_arm()
        self.sim.reset_card()

        if seed is not None:
            np.random.seed(seed)
        offset = np.random.uniform(-0.03, 0.03, size=2)
        self.sim.reset_card([0.15 + offset[0], offset[1], 0.0015])

        return self._get_obs(), {}

    def render(self):
        if self.render_mode == 'rgb_array':
            width, height = 640, 480
            view_matrix = p.computeViewMatrix([0.5, 0.5, 0.3], [0, 0, 0.1], [0, 0, 1])
            proj_matrix = p.computeProjectionMatrixFOV(60, width/height, 0.1, 100)
            _, _, rgb, _, _ = p.getCameraImage(width, height, view_matrix, proj_matrix)
            return np.array(rgb)[:, :, :3]

    def close(self):
        self.sim.close()


if __name__ == "__main__":
    print("Testing stepper+servo hybrid arm (5:1 gearbox on base+shoulder)...")
    env = NexusArmEnv(render_mode='human')
    obs, _ = env.reset()

    for i in range(200):
        action = env.action_space.sample() * 0.3
        obs, reward, term, trunc, info = env.step(action)

        if i % 50 == 0:
            stats = env.sim.get_stepper_stats()
            print(f"Step {i}: Base={stats['base']['angle']:.1f}, Shoulder={stats['shoulder']['angle']:.1f}")

        if term or trunc:
            break

    env.close()
    print("Test complete")
