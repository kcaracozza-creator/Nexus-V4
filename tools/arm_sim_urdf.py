#!/usr/bin/env python3
"""
NEXUS Arm Simulation - URDF Build (PPO_22)
==========================================
Patent Pending - Kevin Caracozza

MODEL: nexus_arm_robo_v3.urdf  (5-DOF, base rotation included)
  Joint 0: Base       Z-axis  +/-180 deg
  Joint 1: Shoulder   Y-axis  -30 to +90 deg
  Joint 2: Elbow      Y-axis  +/-114 deg
  Joint 3: WristRoll  X-axis  +/-180 deg
  Joint 4: WristPitch Y-axis  +/-90 deg
  EE link: 5 (vacuum_gripper, fixed)

FK: PyBullet getLinkState -- no custom math
IK: PyBullet calculateInverseKinematics -- for warm-start & validation

PPO_22 = PPO_22 + SORT milestones:
  - PPO_22 organic eval: 0/100. 100% reach SORT, 100% die there.
  - IK stress test: bin reachable (4.1mm err, 19 steps, 1000 budget).
  - Diagnosis: policy can't find 0.947 rad base pivot (std=3.14 random walk).
  - FIX: SORT milestones at 150mm (+200) and 100mm (+300).
    Same pattern as TRANSPORT milestones. Stepping stones for the pivot.
  - DROP bounty 5K retained. Total SORT payout: 200+300+100+5000 = 5,600.
  - All prior fixes: SORT auto-drop, SCAN_WAIT freeze, split tol, IK HOME reset

TASK FLOW:
  HOME -> PICKUP -> TRANSPORT -> PLACE -> CLEAR -> SCAN_WAIT ->
  RETURN -> RETRIEVE -> SORT (auto-drop on entry) -> DONE
"""

import os
import time
import numpy as np
import pybullet as p
import pybullet_data
import gymnasium as gym
from gymnasium import spaces
from pathlib import Path
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback, BaseCallback
from stable_baselines3.common.monitor import Monitor
import json

# =============================================================================
# URDF PATH
# =============================================================================

URDF_PATH = Path(r"E:\NEXUS_V2_RECREATED\nexus_v2\ai\robot_simulation\nexus_arm_robo_v3.urdf")

# =============================================================================
# JOINT CONFIG  (matches nexus_arm_robo_v3.urdf exactly)
# =============================================================================

NUM_JOINTS       = 5       # controllable revolute joints
EE_LINK_INDEX    = 5       # vacuum_gripper link (fixed joint after wrist_pitch)

JOINT_BASE        = 0
JOINT_SHOULDER    = 1
JOINT_ELBOW       = 2
JOINT_WRIST_ROLL  = 3
JOINT_WRIST_PITCH = 4

# Limits from URDF
JOINT_LIMITS_LOW  = np.array([-3.14159, -0.52, -2.0, -3.14159, -1.57], dtype=np.float32)
JOINT_LIMITS_HIGH = np.array([ 3.14159,  1.57,  2.0,  3.14159,  1.57], dtype=np.float32)

# Home pose (arm pointing straight up, centred)
HOME_JOINTS = np.array([0.0, 0.5, -1.0, 0.0, 0.0], dtype=np.float32)

MAX_STEP_RAD = np.deg2rad(3.0)   # max joint delta per sim step

# =============================================================================
# WORLD POSITIONS  (valid for 5DOF -- base rotation gives full Y reach)
# =============================================================================

CARD_STACK_POS = np.array([ 0.10,  0.00,  0.20], dtype=np.float32)
LIGHTBOX_POS   = np.array([ 0.04,  0.16,  0.05], dtype=np.float32)
CLEAR_POS      = np.array([ 0.00,  0.00,  0.28], dtype=np.float32)
SORT_BIN_POS   = np.array([-0.12,  0.12,  0.05], dtype=np.float32)

# =============================================================================
# TOLERANCES  (curriculum: easy -> final)
# =============================================================================

PLACE_TOLERANCE_FINAL  = 0.020
CLEAR_TOLERANCE_FINAL  = 0.050
PICKUP_TOLERANCE_FINAL = 0.025
DROP_TOLERANCE_FINAL   = 0.025

PLACE_TOLERANCE_EASY  = 0.120
CLEAR_TOLERANCE_EASY  = 0.150
PICKUP_TOLERANCE_EASY = 0.100
DROP_TOLERANCE_EASY   = 0.100

PLACE_TOLERANCE  = PLACE_TOLERANCE_EASY
CLEAR_TOLERANCE  = CLEAR_TOLERANCE_EASY
PICKUP_TOLERANCE = PICKUP_TOLERANCE_EASY
DROP_TOLERANCE   = DROP_TOLERANCE_EASY

CURRICULUM_LEVEL     = 0
CURRICULUM_SUCCESSES = 0
CURRICULUM_EPISODES  = 0
CURRICULUM_WINDOW    = 100
CURRICULUM_THRESHOLD = 0.08
SCAN_STEPS           = 60   # ~2 sec at 30Hz

# =============================================================================
# PHASES
# =============================================================================

PHASE_HOME      = 0
PHASE_PICKUP    = 1
PHASE_TRANSPORT = 2
PHASE_PLACE     = 3
PHASE_CLEAR     = 4
PHASE_SCAN_WAIT = 5
PHASE_RETURN    = 6
PHASE_RETRIEVE  = 7
PHASE_SORT      = 8
PHASE_DROP      = 9

PHASE_NAMES = {
    0: "HOME->STACK",
    1: "PICKUP",
    2: "TRANSPORT->LIGHTBOX",
    3: "PLACE_ON_LIGHTBOX",
    4: "CLEAR_CAMERA",
    5: "SCAN_WAIT",
    6: "RETURN->LIGHTBOX",
    7: "RETRIEVE",
    8: "SORT->BIN",
    9: "DROP_DONE",
}

# =============================================================================
# ENVIRONMENT
# =============================================================================

class NexusArmEnv(gym.Env):
    metadata = {'render_modes': ['human', 'rgb_array']}

    def __init__(self, render_mode=None, max_steps=3000):
        super().__init__()
        self.render_mode = render_mode
        self.max_steps   = max_steps

        # 5D continuous action -- delta joint angles normalised to [-1, 1]
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(NUM_JOINTS,), dtype=np.float32
        )

        # 29D observation:
        #   5 joint pos (normalised) + 5 joint vel + 3 EE pos +
        #   3 EE-to-target vec + 10 phase one-hot +
        #   1 has_card + 1 vacuum + 1 scan_timer_norm
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(29,), dtype=np.float32
        )

        self._physics_client = None
        self._arm_id         = None
        self._lightbox_id    = None
        self._card_id        = None
        self._stack_id       = None
        self._bin_id         = None

        self._joints        = HOME_JOINTS.copy()
        self._phase         = PHASE_HOME
        self._vacuum        = False
        self._solenoid_open = True
        self._has_card      = False
        self._scan_timer    = 0
        self._step_count    = 0
        self._transport_milestone_200 = False
        self._transport_milestone_100 = False
        self._sort_milestone_150 = False
        self._sort_milestone_100 = False
        self._organic_start = True
        self._ee_pos        = np.zeros(3, dtype=np.float32)
        self._prev_dist     = None
        self._last_ee_pos   = None

        # One-and-done milestone flags (reset each phase transition)
        self._reached_close    = False
        self._reached_grip_rng = False

        # Card world position (tracks with EE when held)
        self._card_pos = CARD_STACK_POS.copy()

        # IK cache for warm-start (populated on first reset)
        self._ik_lightbox_joints = None

    # ------------------------------------------------------------------
    # PHYSICS SETUP
    # ------------------------------------------------------------------

    def _setup_physics(self):
        if self._physics_client is not None:
            return

        if self.render_mode == 'human':
            self._physics_client = p.connect(p.GUI)
            p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
        else:
            self._physics_client = p.connect(p.DIRECT)

        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -9.81)
        p.loadURDF("plane.urdf")

        # Load arm
        self._arm_id = p.loadURDF(
            str(URDF_PATH),
            basePosition=[0, 0, 0],
            useFixedBase=True
        )

        # Visual markers -- lightbox, stack, sort bin
        box_shape = p.createVisualShape(p.GEOM_BOX,
            halfExtents=[0.05, 0.05, 0.002],
            rgbaColor=[0.9, 0.9, 0.2, 0.8])
        col_shape = p.createCollisionShape(p.GEOM_BOX,
            halfExtents=[0.05, 0.05, 0.002])
        self._lightbox_id = p.createMultiBody(0, col_shape, box_shape,
            basePosition=LIGHTBOX_POS.tolist())

        stack_vis = p.createVisualShape(p.GEOM_CYLINDER,
            radius=0.03, length=0.04,
            rgbaColor=[0.6, 0.4, 0.2, 0.9])
        stack_col = p.createCollisionShape(p.GEOM_CYLINDER,
            radius=0.03, height=0.04)
        self._stack_id = p.createMultiBody(0, stack_col, stack_vis,
            basePosition=CARD_STACK_POS.tolist())

        bin_vis = p.createVisualShape(p.GEOM_BOX,
            halfExtents=[0.04, 0.04, 0.03],
            rgbaColor=[0.3, 0.6, 0.3, 0.8])
        bin_col = p.createCollisionShape(p.GEOM_BOX,
            halfExtents=[0.04, 0.04, 0.03])
        self._bin_id = p.createMultiBody(0, bin_col, bin_vis,
            basePosition=SORT_BIN_POS.tolist())

        # Card body
        card_vis = p.createVisualShape(p.GEOM_BOX,
            halfExtents=[0.044, 0.032, 0.001],
            rgbaColor=[0.1, 0.5, 0.9, 1.0])
        card_col = p.createCollisionShape(p.GEOM_BOX,
            halfExtents=[0.044, 0.032, 0.001])
        self._card_id = p.createMultiBody(0.005, card_col, card_vis,
            basePosition=CARD_STACK_POS.tolist())

        # Pre-compute IK seeds for all warm-start phases
        self._ik_lightbox_joints = self._solve_ik(LIGHTBOX_POS)
        self._ik_clear_joints    = self._solve_ik(CLEAR_POS)
        self._ik_return_joints   = self._solve_ik(
            LIGHTBOX_POS + np.array([0.0, 0.0, 0.05], dtype=np.float32)
        )
        self._ik_sortbin_joints  = self._solve_ik(
            SORT_BIN_POS + np.array([0.0, 0.0, 0.06], dtype=np.float32)
        )

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _get_ee_pos(self):
        """Read EE world position from PyBullet link state."""
        state = p.getLinkState(self._arm_id, EE_LINK_INDEX,
                               computeForwardKinematics=True)
        return np.array(state[4], dtype=np.float32)

    def _get_joint_states(self):
        states = p.getJointStates(self._arm_id, list(range(NUM_JOINTS)))
        pos = np.array([s[0] for s in states], dtype=np.float32)
        vel = np.array([s[1] for s in states], dtype=np.float32)
        return pos, vel

    def _set_joints(self, joints):
        """Teleport joints (used in reset only)."""
        for i, angle in enumerate(joints):
            p.resetJointState(self._arm_id, i, angle)

    def _apply_action(self, action):
        """Apply delta joint action with velocity control."""
        pos, _ = self._get_joint_states()
        delta   = np.array(action, dtype=np.float32) * MAX_STEP_RAD
        target  = np.clip(pos + delta, JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH)
        for i in range(NUM_JOINTS):
            p.setJointMotorControl2(
                self._arm_id, i,
                p.POSITION_CONTROL,
                targetPosition=float(target[i]),
                force=10.0,
                maxVelocity=2.0
            )
        p.stepSimulation()
        return target

    def _solve_ik(self, target_pos, target_orn=None):
        """PyBullet IK -- returns joint array.

        Resets joints to HOME before solving to avoid contamination
        from previous joint state (PyBullet IK uses current state as seed).
        """
        self._set_joints(HOME_JOINTS)
        p.stepSimulation()

        kwargs = dict(
            bodyUniqueId=self._arm_id,
            endEffectorLinkIndex=EE_LINK_INDEX,
            targetPosition=target_pos.tolist(),
            lowerLimits=JOINT_LIMITS_LOW.tolist(),
            upperLimits=JOINT_LIMITS_HIGH.tolist(),
            jointRanges=(JOINT_LIMITS_HIGH - JOINT_LIMITS_LOW).tolist(),
            restPoses=HOME_JOINTS.tolist(),
            maxNumIterations=200,
            residualThreshold=0.001,
        )
        if target_orn is not None:
            kwargs['targetOrientation'] = target_orn
        result = p.calculateInverseKinematics(**kwargs)
        return np.array(result[:NUM_JOINTS], dtype=np.float32)

    def _get_ee_velocity(self):
        """Linear EE speed from PyBullet getLinkState."""
        state = p.getLinkState(
            self._arm_id, EE_LINK_INDEX,
            computeLinkVelocity=True,
            computeForwardKinematics=True
        )
        lin_vel = np.array(state[6], dtype=np.float32)
        return float(np.linalg.norm(lin_vel))

    def _normalise_joints(self, pos):
        mid   = (JOINT_LIMITS_HIGH + JOINT_LIMITS_LOW) / 2.0
        rng   = (JOINT_LIMITS_HIGH - JOINT_LIMITS_LOW) / 2.0
        return (pos - mid) / rng

    def _phase_target(self):
        # RETRIEVE: approach 40mm above card so vacuum cup descends onto it
        retrieve_target = self._card_pos.copy()
        retrieve_target[2] += 0.04

        targets = {
            PHASE_HOME:      CARD_STACK_POS,
            PHASE_PICKUP:    self._card_pos,
            PHASE_TRANSPORT: LIGHTBOX_POS,
            PHASE_PLACE:     LIGHTBOX_POS,
            PHASE_CLEAR:     CLEAR_POS,
            PHASE_SCAN_WAIT: CLEAR_POS,
            PHASE_RETURN:    LIGHTBOX_POS,
            PHASE_RETRIEVE:  retrieve_target,
            PHASE_SORT:      SORT_BIN_POS,
            PHASE_DROP:      SORT_BIN_POS,
        }
        return targets[self._phase]

    def _update_card_visual(self):
        if self._has_card:
            p.resetBasePositionAndOrientation(
                self._card_id,
                self._ee_pos.tolist(),
                [0, 0, 0, 1]
            )

    # ------------------------------------------------------------------
    # RESET
    # ------------------------------------------------------------------

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        rng = np.random.default_rng(seed)

        self._setup_physics()

        # Random card spawn +/-30mm XY
        card_offset = rng.uniform(-0.03, 0.03, size=2).astype(np.float32)
        self._card_pos = CARD_STACK_POS.copy()
        self._card_pos[0] += card_offset[0]
        self._card_pos[1] += card_offset[1]

        # Reset card body
        p.resetBasePositionAndOrientation(
            self._card_id, self._card_pos.tolist(), [0, 0, 0, 1])

        # --- Warm-start (20% of episodes drop into a late phase) ---
        ik_ready = (self._ik_lightbox_joints is not None and
                    self._ik_clear_joints    is not None and
                    self._ik_return_joints   is not None and
                    self._ik_sortbin_joints  is not None)
        use_warm_start = rng.random() < 0.20 and ik_ready

        if use_warm_start:
            # PPO_17: Only phases 4+ warm-started.
            # HOME->PICKUP->TRANSPORT must be learned organically.
            warm_phase = rng.choice(
                [PHASE_PLACE,
                 PHASE_SCAN_WAIT, PHASE_RETURN,
                 PHASE_RETRIEVE,  PHASE_SORT,  PHASE_DROP],
                p=[0.10, 0.15, 0.25, 0.20, 0.15, 0.15]
            )

            if warm_phase in (PHASE_TRANSPORT, PHASE_PLACE):
                base_joints = self._ik_lightbox_joints
                self._vacuum        = True
                self._solenoid_open = False
                self._has_card      = True

            elif warm_phase == PHASE_SCAN_WAIT:
                base_joints = self._ik_clear_joints
                self._vacuum        = False
                self._solenoid_open = True
                self._has_card      = False
                p.resetBasePositionAndOrientation(
                    self._card_id, LIGHTBOX_POS.tolist(), [0, 0, 0, 1])
                self._card_pos = LIGHTBOX_POS.copy()
                self._scan_timer = 0

            elif warm_phase == PHASE_RETURN:
                base_joints = self._ik_return_joints
                self._vacuum        = False
                self._solenoid_open = True
                self._has_card      = False
                p.resetBasePositionAndOrientation(
                    self._card_id, LIGHTBOX_POS.tolist(), [0, 0, 0, 1])
                self._card_pos = LIGHTBOX_POS.copy()

            elif warm_phase == PHASE_RETRIEVE:
                retrieve_above = LIGHTBOX_POS.copy()
                retrieve_above[2] += 0.04
                base_joints = self._solve_ik(retrieve_above)
                if base_joints is None:
                    base_joints = self._ik_return_joints
                    warm_phase  = PHASE_RETURN
                self._vacuum        = False
                self._solenoid_open = True
                self._has_card      = False
                p.resetBasePositionAndOrientation(
                    self._card_id, LIGHTBOX_POS.tolist(), [0, 0, 0, 1])
                self._card_pos = LIGHTBOX_POS.copy()

            elif warm_phase == PHASE_SORT:
                base_joints = self._ik_sortbin_joints
                self._vacuum        = True
                self._solenoid_open = False
                self._has_card      = True
                p.resetBasePositionAndOrientation(
                    self._card_id, SORT_BIN_POS.tolist(), [0, 0, 0, 1])
                self._card_pos = SORT_BIN_POS.copy()

            else:  # PHASE_DROP
                drop_above = SORT_BIN_POS.copy()
                drop_above[2] += 0.02
                base_joints = self._solve_ik(drop_above)
                if base_joints is None:
                    base_joints = self._ik_sortbin_joints
                    warm_phase  = PHASE_SORT
                self._vacuum        = True
                self._solenoid_open = False
                self._has_card      = True
                p.resetBasePositionAndOrientation(
                    self._card_id, drop_above.tolist(), [0, 0, 0, 1])
                self._card_pos = drop_above.copy()

            noise       = rng.uniform(-0.05, 0.05, size=NUM_JOINTS).astype(np.float32)
            warm_joints = np.clip(base_joints + noise, JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH)
            self._set_joints(warm_joints)
            self._joints = warm_joints.copy()
            self._phase  = warm_phase
            self._reached_close    = True
            self._reached_grip_rng = True
            self._organic_start = False  # Warm-started -- use curriculum tolerance
        else:
            self._set_joints(HOME_JOINTS)
            self._joints        = HOME_JOINTS.copy()
            self._vacuum        = False
            self._solenoid_open = True
            self._has_card      = False
            self._phase         = PHASE_HOME
            self._reached_close    = False
            self._reached_grip_rng = False
            self._organic_start = True   # Cold start -- EASY tolerances for ALL phases

        self._scan_timer  = 0
        self._step_count  = 0
        self._last_ee_pos = None
        self._transport_milestone_200 = False
        self._transport_milestone_100 = False
        self._sort_milestone_150 = False
        self._sort_milestone_100 = False

        p.stepSimulation()
        self._ee_pos  = self._get_ee_pos()
        self._prev_dist = float(np.linalg.norm(self._ee_pos - self._phase_target()))

        # Only snap card to EE for phases where arm is holding it
        if use_warm_start and warm_phase in (PHASE_TRANSPORT, PHASE_PLACE):
            self._card_pos = self._ee_pos.copy()
            p.resetBasePositionAndOrientation(
                self._card_id, self._card_pos.tolist(), [0, 0, 0, 1])

        return self._get_obs(), {}

    # ------------------------------------------------------------------
    # OBSERVATION
    # ------------------------------------------------------------------

    def _get_obs(self):
        pos, vel  = self._get_joint_states()
        jpos_norm = self._normalise_joints(pos)
        target    = self._phase_target()
        ee_to_tgt = target - self._ee_pos

        phase_oh  = np.zeros(10, dtype=np.float32)
        phase_oh[self._phase] = 1.0

        scan_norm = float(self._scan_timer) / float(SCAN_STEPS)

        obs = np.concatenate([
            jpos_norm,                          # 5
            np.clip(vel / 5.0, -1, 1),          # 5
            self._ee_pos,                       # 3
            ee_to_tgt,                          # 3
            phase_oh,                           # 10
            [float(self._has_card)],            # 1
            [float(self._vacuum)],              # 1
            [scan_norm],                        # 1
        ]).astype(np.float32)
        return obs

    # ------------------------------------------------------------------
    # STEP
    # ------------------------------------------------------------------

    def step(self, action):
        self._step_count += 1
        self._last_ee_pos = self._ee_pos.copy() if self._last_ee_pos is None \
                            else self._last_ee_pos

        # SCAN_WAIT: freeze action -- hold joints at current position.
        # Hardware behavior, not a learned skill. Kills 66% loitering.
        if self._phase == PHASE_SCAN_WAIT:
            pos, _ = self._get_joint_states()
            for i in range(NUM_JOINTS):
                p.setJointMotorControl2(
                    self._arm_id, i,
                    p.POSITION_CONTROL,
                    targetPosition=float(pos[i]),
                    force=10.0,
                    maxVelocity=0.0
                )
            p.stepSimulation()
        else:
            self._joints = self._apply_action(action)
        prev_ee      = self._ee_pos.copy()
        self._ee_pos = self._get_ee_pos()

        if self._has_card:
            self._card_pos = self._ee_pos.copy()
            self._update_card_visual()

        reward, done, info = self._update_phase()

        truncated = self._step_count >= self.max_steps
        obs       = self._get_obs()
        return obs, reward, done, truncated, info

    # ------------------------------------------------------------------
    # PHASE LOGIC + REWARD
    # ------------------------------------------------------------------

    def _update_phase(self):
        target  = self._phase_target()
        dist    = float(np.linalg.norm(self._ee_pos - target))
        reward  = 0.0
        done    = False
        info    = {'phase': PHASE_NAMES[self._phase], 'dist': dist}

        # Per-step penalty
        reward -= 0.01

        # Dense shaping: distance improvement (ON for all phases including SORT)
        # SORT auto-drops on tolerance entry — no camping possible with done=True
        if self._prev_dist is not None:
            reward += (self._prev_dist - dist) * 10.0
        self._prev_dist = dist

        # One-and-done milestones
        if not self._reached_close and dist < 0.04:
            reward += 100.0
            self._reached_close = True
            info['event'] = 'MILESTONE_CLOSE'

        if not self._reached_grip_rng and dist < 0.02:
            reward += 150.0
            self._reached_grip_rng = True
            info['event'] = 'MILESTONE_GRIP_RANGE'

        # ---- Phase transitions ----
        # PPO_17: ALL phases split -- organic=EASY, warm=curriculum

        if self._phase == PHASE_HOME:
            tol = PICKUP_TOLERANCE_EASY if self._organic_start else PICKUP_TOLERANCE
            if dist < tol:
                reward += 50.0
                self._phase = PHASE_PICKUP
                self._reached_close = False
                self._reached_grip_rng = False
                info['event'] = 'PHASE_HOME_DONE'

        elif self._phase == PHASE_PICKUP:
            tol = PICKUP_TOLERANCE_EASY if self._organic_start else PICKUP_TOLERANCE
            if dist < tol and not self._vacuum:
                self._vacuum        = True
                self._solenoid_open = False
                self._has_card      = True
                self._card_pos      = self._ee_pos.copy()
                reward += 200.0
                self._phase = PHASE_TRANSPORT
                self._reached_close = False
                self._reached_grip_rng = False
                self._prev_dist = None
                info['event'] = 'PICKUP_SUCCESS'

        elif self._phase == PHASE_TRANSPORT:
            tol = PLACE_TOLERANCE_EASY if self._organic_start else PLACE_TOLERANCE
            if not self._transport_milestone_200 and dist < 0.200:
                reward += 50.0
                self._transport_milestone_200 = True
            if not self._transport_milestone_100 and dist < 0.150:
                reward += 150.0
                self._transport_milestone_100 = True
            if dist < tol:
                reward += 100.0
                self._phase = PHASE_PLACE
                self._reached_close = False
                self._reached_grip_rng = False
                self._transport_milestone_200 = False
                self._transport_milestone_100 = False
                self._prev_dist = None
                info['event'] = 'TRANSPORT_DONE'

        elif self._phase == PHASE_PLACE:
            tol = PLACE_TOLERANCE_EASY if self._organic_start else PLACE_TOLERANCE
            if dist < tol:
                self._vacuum        = False
                self._solenoid_open = True
                self._has_card      = False
                p.resetBasePositionAndOrientation(
                    self._card_id, LIGHTBOX_POS.tolist(), [0, 0, 0, 1])
                self._card_pos = LIGHTBOX_POS.copy()
                reward += 500.0
                self._phase = PHASE_CLEAR
                self._reached_close = False
                self._reached_grip_rng = False
                self._prev_dist = None
                info['event'] = 'PLACE_SUCCESS'

        elif self._phase == PHASE_CLEAR:
            tol = CLEAR_TOLERANCE_EASY if self._organic_start else CLEAR_TOLERANCE
            if dist < tol:
                reward += 200.0
                self._phase = PHASE_SCAN_WAIT
                self._scan_timer = 0
                self._reached_close = False
                self._reached_grip_rng = False
                info['event'] = 'CLEAR_SUCCESS'

        elif self._phase == PHASE_SCAN_WAIT:
            # Action is frozen in step() -- timer always increments
            self._scan_timer += 1
            reward += 1.0

            if self._scan_timer >= SCAN_STEPS:
                reward += 300.0
                self._phase = PHASE_RETURN
                self._reached_close = False
                self._reached_grip_rng = False
                info['event'] = 'SCAN_COMPLETE'

        elif self._phase == PHASE_RETURN:
            tol = PLACE_TOLERANCE_EASY if self._organic_start else PLACE_TOLERANCE
            if dist < tol:
                reward += 100.0
                self._phase = PHASE_RETRIEVE
                self._reached_close = False
                self._reached_grip_rng = False
                self._prev_dist = None
                info['event'] = 'RETURN_DONE'

        elif self._phase == PHASE_RETRIEVE:
            tol = PICKUP_TOLERANCE_EASY if self._organic_start else PICKUP_TOLERANCE
            if dist < tol:
                self._vacuum        = True
                self._solenoid_open = False
                self._has_card      = True
                self._card_pos      = self._ee_pos.copy()
                reward += 200.0
                self._phase = PHASE_SORT
                self._reached_close = False
                self._reached_grip_rng = False
                self._prev_dist = None
                info['event'] = 'RETRIEVE_SUCCESS'

        elif self._phase == PHASE_SORT:
            # SORT milestones — stepping stones for the 0.947 rad base pivot
            if not self._sort_milestone_150 and dist < 0.150:
                reward += 200.0
                self._sort_milestone_150 = True
            if not self._sort_milestone_100 and dist < 0.100:
                reward += 300.0
                self._sort_milestone_100 = True
            tol = DROP_TOLERANCE_EASY if self._organic_start else DROP_TOLERANCE
            if dist < tol:
                # Auto-execute drop on SORT success — no intermediate PHASE_DROP.
                # Two-phase SORT->DROP created a camping exploit: agent collected
                # dense shaping at SORT_BIN forever without committing to release.
                # Merging phases eliminates the campsite.
                self._vacuum        = False
                self._solenoid_open = True
                self._has_card      = False
                p.resetBasePositionAndOrientation(
                    self._card_id, SORT_BIN_POS.tolist(), [0, 0, 0, 1])
                reward += 100.0 + 5000.0   # SORT bonus + DROP bonus (5K = 16x next highest)
                done = True
                self._prev_dist = None
                info['event'] = 'FULL_CYCLE_COMPLETE'

        elif self._phase == PHASE_DROP:
            # Dead code — SORT auto-drops now. Kept for warm-start compatibility.
            tol = DROP_TOLERANCE_EASY if self._organic_start else DROP_TOLERANCE
            if dist < tol:
                self._vacuum        = False
                self._solenoid_open = True
                self._has_card      = False
                p.resetBasePositionAndOrientation(
                    self._card_id, SORT_BIN_POS.tolist(), [0, 0, 0, 1])
                reward += 5000.0
                done = True
                info['event'] = 'FULL_CYCLE_COMPLETE'

        # Card drop penalty
        if self._has_card:
            card_world_pos, _ = p.getBasePositionAndOrientation(self._card_id)
            if card_world_pos[2] < -0.01:
                reward -= 100.0
                self._has_card = False
                info['event'] = 'CARD_DROPPED'

        return reward, done, info

    # ------------------------------------------------------------------
    # RENDER / CLOSE
    # ------------------------------------------------------------------

    def render(self):
        if self.render_mode == 'rgb_array':
            w, h = 640, 480
            view = p.computeViewMatrixFromYawPitchRoll(
                cameraTargetPosition=[0.1, 0.1, 0.1],
                distance=0.6, yaw=45, pitch=-30, roll=0,
                upAxisIndex=2)
            proj = p.computeProjectionMatrixFOV(
                fov=60, aspect=w/h, nearVal=0.01, farVal=2.0)
            _, _, rgb, _, _ = p.getCameraImage(w, h, view, proj)
            return np.array(rgb, dtype=np.uint8)[:, :, :3]

    def close(self):
        if self._physics_client is not None:
            p.disconnect(self._physics_client)
            self._physics_client = None


# =============================================================================
# CURRICULUM CALLBACK
# =============================================================================

class CurriculumCallback(BaseCallback):
    def __init__(self, verbose=0):
        super().__init__(verbose)
        self._ep_rewards = []
        self._ep_lengths = []

    def _on_step(self):
        global PLACE_TOLERANCE, CLEAR_TOLERANCE, PICKUP_TOLERANCE, DROP_TOLERANCE
        global CURRICULUM_LEVEL, CURRICULUM_SUCCESSES, CURRICULUM_EPISODES

        for info in self.locals.get('infos', []):
            if info.get('event') == 'FULL_CYCLE_COMPLETE':
                CURRICULUM_SUCCESSES += 1
            if 'episode' in info:
                CURRICULUM_EPISODES += 1

        if CURRICULUM_EPISODES >= CURRICULUM_WINDOW:
            rate = CURRICULUM_SUCCESSES / CURRICULUM_EPISODES
            if rate >= CURRICULUM_THRESHOLD and CURRICULUM_LEVEL < 10:
                CURRICULUM_LEVEL += 1
                t = CURRICULUM_LEVEL / 10.0
                PLACE_TOLERANCE  = PLACE_TOLERANCE_EASY  + t * (PLACE_TOLERANCE_FINAL  - PLACE_TOLERANCE_EASY)
                CLEAR_TOLERANCE  = CLEAR_TOLERANCE_EASY  + t * (CLEAR_TOLERANCE_FINAL  - CLEAR_TOLERANCE_EASY)
                PICKUP_TOLERANCE = PICKUP_TOLERANCE_EASY + t * (PICKUP_TOLERANCE_FINAL - PICKUP_TOLERANCE_EASY)
                DROP_TOLERANCE   = DROP_TOLERANCE_EASY   + t * (DROP_TOLERANCE_FINAL   - DROP_TOLERANCE_EASY)
                if self.verbose:
                    print(f"\n[CURRICULUM] Level {CURRICULUM_LEVEL}/10  "
                          f"place={PLACE_TOLERANCE*1000:.0f}mm  "
                          f"pickup={PICKUP_TOLERANCE*1000:.0f}mm")

            CURRICULUM_SUCCESSES = 0
            CURRICULUM_EPISODES  = 0

        return True


# =============================================================================
# TRAINING STATS CALLBACK
# =============================================================================

class StatsCallback(BaseCallback):
    def __init__(self, log_path, verbose=0):
        super().__init__(verbose)
        self.log_path    = Path(log_path)
        self._ep_rewards = []
        self._ep_lengths = []
        self._phases_hit = {n: 0 for n in PHASE_NAMES.values()}

    def _on_step(self):
        for info in self.locals.get('infos', []):
            phase = info.get('phase')
            if phase and phase in self._phases_hit:
                self._phases_hit[phase] += 1
            if 'episode' in info:
                self._ep_rewards.append(info['episode']['r'])
                self._ep_lengths.append(info['episode']['l'])

        if self.num_timesteps % 32768 == 0 and self._ep_rewards:
            stats = {
                'timesteps':     self.num_timesteps,
                'ep_rew_mean':   float(np.mean(self._ep_rewards[-100:])),
                'ep_len_mean':   float(np.mean(self._ep_lengths[-100:])),
                'phases_hit':    self._phases_hit.copy(),
                'curriculum_lvl': CURRICULUM_LEVEL,
            }
            self.log_path.write_text(json.dumps(stats, indent=2))
        return True


# =============================================================================
# MAIN
# =============================================================================

def make_env(rank, render_mode=None):
    def _init():
        env = NexusArmEnv(render_mode=render_mode if rank == 0 else None)
        env = Monitor(env)
        return env
    return _init


def set_curriculum_level(level):
    """Set global tolerances to match a curriculum level (0-10)."""
    global PLACE_TOLERANCE, CLEAR_TOLERANCE, PICKUP_TOLERANCE, DROP_TOLERANCE
    global CURRICULUM_LEVEL
    CURRICULUM_LEVEL = level
    t = level / 10.0
    PLACE_TOLERANCE  = PLACE_TOLERANCE_EASY  + t * (PLACE_TOLERANCE_FINAL  - PLACE_TOLERANCE_EASY)
    CLEAR_TOLERANCE  = CLEAR_TOLERANCE_EASY  + t * (CLEAR_TOLERANCE_FINAL  - CLEAR_TOLERANCE_EASY)
    PICKUP_TOLERANCE = PICKUP_TOLERANCE_EASY + t * (PICKUP_TOLERANCE_FINAL - PICKUP_TOLERANCE_EASY)
    DROP_TOLERANCE   = DROP_TOLERANCE_EASY   + t * (DROP_TOLERANCE_FINAL   - DROP_TOLERANCE_EASY)


if __name__ == '__main__':
    import sys
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps',  type=int, default=5_000_000)
    parser.add_argument('--envs',   type=int, default=16)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--load',   type=str, default=None,
                        help='Load weights from checkpoint .zip')
    args = parser.parse_args()

    BASE_DIR  = Path(r"E:\NEXUS_V2_RECREATED\training")
    CKPT_DIR  = BASE_DIR / "arm_checkpoints_urdf"
    LOG_DIR   = BASE_DIR / "arm_logs_urdf"
    STATS_FILE = BASE_DIR / "training_stats.json"
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Validate URDF exists before spawning 16 processes
    if not URDF_PATH.exists():
        raise FileNotFoundError(f"URDF not found: {URDF_PATH}")
    print(f"URDF: {URDF_PATH}")
    print(f"Joints: {NUM_JOINTS}-DOF  |  EE link: {EE_LINK_INDEX}")
    print(f"Envs: {args.envs}  |  Steps: {args.steps:,}")

    # If loading from checkpoint, start at Level 10
    if args.load:
        load_path = Path(args.load)
        if not load_path.exists():
            load_path = BASE_DIR / args.load
        if not load_path.exists():
            print(f"Checkpoint not found: {args.load}")
            sys.exit(1)
        set_curriculum_level(10)
        print(f"\nLoading checkpoint: {load_path}")
        print(f"Curriculum: Level 10 (warm-start tolerances locked to final)")
        print(f"  PLACE:  {PLACE_TOLERANCE*1000:.0f}mm  (organic: {PLACE_TOLERANCE_EASY*1000:.0f}mm)")
        print(f"  PICKUP: {PICKUP_TOLERANCE*1000:.0f}mm  (organic: {PICKUP_TOLERANCE_EASY*1000:.0f}mm)")
        print(f"  DROP:   {DROP_TOLERANCE*1000:.0f}mm  (organic: {DROP_TOLERANCE_EASY*1000:.0f}mm)")
        print(f"  CLEAR:  {CLEAR_TOLERANCE*1000:.0f}mm  (organic: {CLEAR_TOLERANCE_EASY*1000:.0f}mm)")

    # Quick single-env IK sanity check before spawning
    print("\nRunning IK sanity check...")
    test_env = NexusArmEnv()
    test_env.reset()

    all_ok = True
    targets = {
        'CARD_STACK': CARD_STACK_POS,
        'LIGHTBOX':   LIGHTBOX_POS,
        'CLEAR':      CLEAR_POS,
        'SORT_BIN':   SORT_BIN_POS,
    }
    for name, tgt in targets.items():
        ik_sol = test_env._solve_ik(tgt)
        test_env._set_joints(ik_sol)
        p.stepSimulation(test_env._physics_client)
        ee = test_env._get_ee_pos()
        err_mm = float(np.linalg.norm(ee - tgt)) * 1000
        status = 'OK' if err_mm < 30 else '*** WARN: >30mm'
        if err_mm >= 30:
            all_ok = False
        print(f"  {name:12s}  target={np.round(tgt,3)}  ee={np.round(ee,4)}  err={err_mm:.1f}mm  {status}")

    if not all_ok:
        print("\n*** ABORT: IK failed on one or more targets ***")
        test_env.close()
        sys.exit(1)

    # ---- RETRIEVE->SORT stress test ----
    # The standard check solves IK from HOME. But during an episode the arm
    # arrives at SORT from RETRIEVE (lightbox config). Test if IK can reach
    # SORT_BIN from the lightbox joint state WITHOUT resetting to HOME first.
    print("\n  RETRIEVE->SORT pivot stress test:")
    lb_joints = test_env._solve_ik(LIGHTBOX_POS)
    test_env._set_joints(lb_joints)
    p.stepSimulation(test_env._physics_client)
    lb_ee = test_env._get_ee_pos()
    print(f"    Start: LIGHTBOX joints={np.round(lb_joints,3)}  ee={np.round(lb_ee,4)}")

    # Raw IK from lightbox config (skip HOME reset)
    raw_kwargs = dict(
        bodyUniqueId=test_env._arm_id,
        endEffectorLinkIndex=EE_LINK_INDEX,
        targetPosition=SORT_BIN_POS.tolist(),
        lowerLimits=JOINT_LIMITS_LOW.tolist(),
        upperLimits=JOINT_LIMITS_HIGH.tolist(),
        jointRanges=(JOINT_LIMITS_HIGH - JOINT_LIMITS_LOW).tolist(),
        restPoses=lb_joints.tolist(),  # rest = lightbox, not HOME
        maxNumIterations=200,
        residualThreshold=0.001,
    )
    raw_sol = np.array(
        p.calculateInverseKinematics(**raw_kwargs)[:NUM_JOINTS],
        dtype=np.float32)
    test_env._set_joints(raw_sol)
    p.stepSimulation(test_env._physics_client)
    raw_ee = test_env._get_ee_pos()
    raw_err = float(np.linalg.norm(raw_ee - SORT_BIN_POS)) * 1000

    # Joint delta required
    delta_rad = np.abs(raw_sol - lb_joints)
    max_delta = float(np.max(delta_rad))
    steps_needed = int(np.ceil(max_delta / 0.05))  # action scale = 0.05 rad/step

    status = 'OK' if raw_err < 30 else '*** UNREACHABLE'
    print(f"    Target: SORT_BIN  sol={np.round(raw_sol,3)}  ee={np.round(raw_ee,4)}  err={raw_err:.1f}mm  {status}")
    print(f"    Joint delta: {np.round(delta_rad,3)} rad  max={max_delta:.3f} rad")
    print(f"    Min steps at 0.05 rad/step: {steps_needed}")
    if raw_err >= 30:
        print("    *** SORT_BIN is UNREACHABLE from lightbox config! ***")
        all_ok = False

    # Also check: what's the base rotation needed?
    base_delta = abs(float(raw_sol[0] - lb_joints[0]))
    print(f"    Base pivot: {base_delta:.3f} rad ({np.degrees(base_delta):.1f} deg)")

    print("\nAll targets OK -- safe to spawn.\n")
    test_env.close()

    n_envs = args.envs
    vec_env = SubprocVecEnv([make_env(i) for i in range(n_envs)], start_method='spawn')

    if args.load:
        model = PPO.load(
            str(load_path),
            env=vec_env,
            verbose=1,
            learning_rate=5e-5,
            ent_coef=0.001,
            tensorboard_log=str(LOG_DIR),
        )
        print(f"Loaded weights from: {load_path}")
        print(f"Overrides: learning_rate=5e-5, ent_coef=0.001")
    else:
        model = PPO(
            "MlpPolicy",
            vec_env,
            verbose=1,
            learning_rate=5e-5,
            n_steps=2048,
            batch_size=512,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.15,
            ent_coef=0.001,
            vf_coef=0.5,
            max_grad_norm=0.5,
            tensorboard_log=str(LOG_DIR),
        )

    callbacks = [
        CheckpointCallback(
            save_freq=max(400_000 // n_envs, 1),
            save_path=str(CKPT_DIR),
            name_prefix="nexus_arm_urdf",
        ),
        CurriculumCallback(verbose=1),
        StatsCallback(log_path=STATS_FILE, verbose=1),
    ]

    print("\nLaunching PPO_22...\n")
    model.learn(
        total_timesteps=args.steps,
        callback=callbacks,
        tb_log_name="PPO_22",
    )

    final_path = CKPT_DIR / "nexus_arm_urdf_final.zip"
    model.save(str(final_path))
    print(f"\nSaved: {final_path}")
    vec_env.close()
