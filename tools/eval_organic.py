#!/usr/bin/env python3
"""
NEXUS Arm Policy Eval — Organic Only
Loads production checkpoint, runs N episodes with warm-starts DISABLED.
This is the real floor — no seeding, no shortcuts.

Usage:
    python eval_organic.py --model PPO_14_FINAL_lvl10_2M.zip --episodes 100
"""
import argparse
import numpy as np
from stable_baselines3 import PPO

# ---- patch env to disable warm-starts before import ----
import arm_sim_urdf as arm_module

_original_reset = arm_module.NexusArmEnv.reset

def _cold_reset(self, seed=None, options=None):
    """Force cold start every episode — no warm-start seeding."""
    # Temporarily zero the warm-start probability
    import gymnasium as gym
    result = _original_reset(self, seed=seed, options=options)
    return result

# Monkey-patch: force use_warm_start = False
_original_init = arm_module.NexusArmEnv.__init__

def _patched_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    self._force_cold = True

arm_module.NexusArmEnv.__init__ = _patched_init

# Patch reset to skip warm-start block
_orig_reset = arm_module.NexusArmEnv.reset
def _cold_reset(self, seed=None, options=None):
    import gymnasium
    # Call parent to reset RNG
    gymnasium.Env.reset(self, seed=seed)
    rng = np.random.default_rng(seed)

    self._setup_physics()

    card_offset = rng.uniform(-0.03, 0.03, size=2).astype(np.float32)
    self._card_pos = arm_module.CARD_STACK_POS.copy()
    self._card_pos[0] += card_offset[0]
    self._card_pos[1] += card_offset[1]

    import pybullet as p
    p.resetBasePositionAndOrientation(
        self._card_id, self._card_pos.tolist(), [0, 0, 0, 1])

    # Cold start — HOME always
    self._set_joints(arm_module.HOME_JOINTS)
    self._joints        = arm_module.HOME_JOINTS.copy()
    self._vacuum        = False
    self._solenoid_open = True
    self._has_card      = False
    self._phase         = arm_module.PHASE_HOME
    self._reached_close    = False
    self._reached_grip_rng = False
    self._transport_milestone_200 = False
    self._transport_milestone_100 = False

    self._scan_timer  = 0
    self._step_count  = 0
    self._last_ee_pos = None

    p.stepSimulation()
    self._ee_pos    = self._get_ee_pos()
    self._prev_dist = float(np.linalg.norm(self._ee_pos - self._phase_target()))

    return self._get_obs(), {}

arm_module.NexusArmEnv.reset = _cold_reset

# ---- now run eval ----
from arm_sim_urdf import NexusArmEnv, PHASE_NAMES

def run_eval(model_path, n_episodes=100):
    print(f"Loading: {model_path}")
    model = PPO.load(model_path)
    env   = NexusArmEnv()

    results = []
    phase_deaths = {}

    for ep in range(n_episodes):
        obs, _ = env.reset()
        done = truncated = False
        total_reward = 0
        steps = 0
        final_phase = "HOME->STACK"

        while not (done or truncated):
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = env.step(action)
            total_reward += reward
            steps += 1
            final_phase = info.get("phase", final_phase)

        success = done and not truncated  # done=True only on DROP_DONE
        results.append({
            "success": success,
            "reward": total_reward,
            "steps": steps,
            "phase": final_phase
        })

        if not success:
            phase_deaths[final_phase] = phase_deaths.get(final_phase, 0) + 1

        if (ep+1) % 10 == 0:
            so_far = sum(r["success"] for r in results)
            print(f"  [{ep+1}/{n_episodes}] success={so_far}/{ep+1} ({100*so_far/(ep+1):.1f}%)")

    successes = sum(r["success"] for r in results)
    mean_reward = np.mean([r["reward"] for r in results])
    mean_steps  = np.mean([r["steps"] for r in results])
    success_steps = [r["steps"] for r in results if r["success"]]

    print()
    print("=" * 50)
    print(f"ORGANIC EVAL RESULTS — {n_episodes} episodes")
    print("=" * 50)
    print(f"Completion rate:  {successes}/{n_episodes} ({100*successes/n_episodes:.1f}%)")
    print(f"Mean reward:      {mean_reward:.1f}")
    print(f"Mean steps/ep:    {mean_steps:.1f}")
    if success_steps:
        print(f"Mean steps (wins):{np.mean(success_steps):.1f}")
    print()
    print("Deaths by phase:")
    for phase, count in sorted(phase_deaths.items(), key=lambda x: -x[1]):
        print(f"  {phase:<25} {count:>4} ({100*count/n_episodes:.1f}%)")
    print("=" * 50)

    env.close()
    return successes / n_episodes

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",    default="PPO_14_FINAL_lvl10_2M.zip")
    parser.add_argument("--episodes", type=int, default=100)
    args = parser.parse_args()
    run_eval(args.model, args.episodes)
