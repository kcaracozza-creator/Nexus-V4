#!/usr/bin/env python3
"""
NEXUS Arm Policy Evaluator
===========================
Runs N episodes at Level 10 (final) tolerances. Cold-start only —
no warm-start seeding. Reports completion %, phase breakdown, and
per-phase conversion rates.

Usage:
  python eval_arm_policy.py                         # latest final model
  python eval_arm_policy.py --model path/to/ckpt.zip
  python eval_arm_policy.py --episodes 200
  python eval_arm_policy.py --render                # GUI mode (slow)
"""

import sys
import argparse
import time
import numpy as np
from pathlib import Path
from collections import defaultdict

# Import everything from the training script
sys.path.insert(0, str(Path(__file__).parent))
import arm_sim_urdf as sim

from stable_baselines3 import PPO


def set_level10_tolerances():
    """Lock tolerances to curriculum Level 10 (final production values)."""
    sim.PLACE_TOLERANCE  = sim.PLACE_TOLERANCE_FINAL    # 20mm
    sim.CLEAR_TOLERANCE  = sim.CLEAR_TOLERANCE_FINAL    # 50mm
    sim.PICKUP_TOLERANCE = sim.PICKUP_TOLERANCE_FINAL   # 25mm
    sim.DROP_TOLERANCE   = sim.DROP_TOLERANCE_FINAL     # 25mm
    sim.CURRICULUM_LEVEL = 10


class ColdStartEnv(sim.NexusArmEnv):
    """Eval wrapper — forces cold-start (HOME phase) on every reset."""

    def reset(self, seed=None, options=None):
        # Keep resetting until we get a cold-start episode
        for _ in range(20):
            obs, info = super().reset(seed=seed, options=options)
            if self._phase == sim.PHASE_HOME:
                return obs, info
            seed = None  # vary seed on retry
        # Shouldn't happen (50% chance each try → ~1e-6 fail rate in 20)
        raise RuntimeError("Failed to get cold-start episode in 20 tries")


def run_eval(model_path, n_episodes=100, render=False):
    set_level10_tolerances()

    print("=" * 60)
    print("NEXUS Arm Policy Eval — Level 10 Tolerances (Cold Start)")
    print("=" * 60)
    print(f"Model:    {model_path}")
    print(f"Episodes: {n_episodes}")
    print(f"Tolerances (final):")
    print(f"  PLACE:  {sim.PLACE_TOLERANCE*1000:.0f}mm")
    print(f"  CLEAR:  {sim.CLEAR_TOLERANCE*1000:.0f}mm")
    print(f"  PICKUP: {sim.PICKUP_TOLERANCE*1000:.0f}mm")
    print(f"  DROP:   {sim.DROP_TOLERANCE*1000:.0f}mm")
    print()

    # Load model
    model = PPO.load(str(model_path))
    env = ColdStartEnv(render_mode='human' if render else None)

    # Tracking
    full_cycles     = 0
    total_reward    = 0.0
    total_steps     = 0
    max_phase_per_ep = []      # highest phase reached per episode
    phase_entries    = defaultdict(int)  # how many episodes entered each phase
    phase_times      = defaultdict(list) # steps spent in each phase per episode
    timeouts         = 0
    rewards_list     = []
    lengths_list     = []

    t0 = time.time()

    for ep in range(n_episodes):
        obs, _ = env.reset()
        ep_reward = 0.0
        ep_steps  = 0
        ep_max_phase = 0
        ep_phase_steps = defaultdict(int)
        entered_phases = set()
        done = False
        truncated = False

        while not done and not truncated:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = env.step(action)
            ep_reward += reward
            ep_steps  += 1

            phase_idx = list(sim.PHASE_NAMES.keys())[
                list(sim.PHASE_NAMES.values()).index(info['phase'])
            ] if info.get('phase') in sim.PHASE_NAMES.values() else 0
            ep_max_phase = max(ep_max_phase, phase_idx)
            ep_phase_steps[phase_idx] += 1

            if phase_idx not in entered_phases:
                entered_phases.add(phase_idx)
                phase_entries[phase_idx] += 1

        if done and info.get('event') == 'FULL_CYCLE_COMPLETE':
            full_cycles += 1

        if truncated and not done:
            timeouts += 1

        total_reward += ep_reward
        total_steps  += ep_steps
        max_phase_per_ep.append(ep_max_phase)
        rewards_list.append(ep_reward)
        lengths_list.append(ep_steps)

        for ph, steps in ep_phase_steps.items():
            phase_times[ph].append(steps)

        # Progress
        pct = (ep + 1) / n_episodes * 100
        status = "COMPLETE" if done else "TIMEOUT"
        phase_name = sim.PHASE_NAMES.get(ep_max_phase, "?")
        if (ep + 1) % 10 == 0 or ep == 0:
            print(f"  [{ep+1:3d}/{n_episodes}] {pct:5.1f}%  "
                  f"cycles={full_cycles}  last={status}  "
                  f"max_phase={phase_name}  rew={ep_reward:.0f}  "
                  f"steps={ep_steps}")

    elapsed = time.time() - t0
    env.close()

    # ---- Report ----
    completion_rate = full_cycles / n_episodes * 100

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Full cycles:      {full_cycles}/{n_episodes}  "
          f"({completion_rate:.1f}%)")
    print(f"Timeouts:         {timeouts}/{n_episodes}")
    print(f"Avg reward:       {np.mean(rewards_list):.1f}  "
          f"(std {np.std(rewards_list):.1f})")
    print(f"Avg ep length:    {np.mean(lengths_list):.0f}  "
          f"(std {np.std(lengths_list):.0f})")
    print(f"Eval time:        {elapsed:.1f}s  "
          f"({elapsed/n_episodes:.2f}s/ep)")

    # Phase reach distribution
    print()
    print("Phase reached (max per episode):")
    phase_counts = defaultdict(int)
    for mp in max_phase_per_ep:
        phase_counts[mp] += 1
    for ph_idx in range(10):
        name  = sim.PHASE_NAMES.get(ph_idx, "?")
        count = phase_counts.get(ph_idx, 0)
        bar   = "#" * (count * 40 // max(n_episodes, 1))
        print(f"  {name:22s}  {count:4d}  ({count/n_episodes*100:5.1f}%)  {bar}")

    # Phase entry conversion funnel
    print()
    print("Phase entry funnel (episodes entering each phase):")
    for ph_idx in range(10):
        name  = sim.PHASE_NAMES.get(ph_idx, "?")
        count = phase_entries.get(ph_idx, 0)
        pct   = count / n_episodes * 100
        bar   = "#" * (count * 40 // max(n_episodes, 1))
        print(f"  {name:22s}  {count:4d}/{n_episodes}  "
              f"({pct:5.1f}%)  {bar}")

    # Conversion rates between consecutive phases
    print()
    print("Phase-to-phase conversion rates:")
    for ph_idx in range(9):
        curr_name = sim.PHASE_NAMES.get(ph_idx, "?")
        next_name = sim.PHASE_NAMES.get(ph_idx + 1, "?")
        curr_entries = phase_entries.get(ph_idx, 0)
        next_entries = phase_entries.get(ph_idx + 1, 0)
        if curr_entries > 0:
            conv = next_entries / curr_entries * 100
            print(f"  {curr_name:22s} -> {next_name:22s}  "
                  f"{next_entries:4d}/{curr_entries:4d}  ({conv:5.1f}%)")

    # Avg time in each phase
    print()
    print("Avg steps per phase (when entered):")
    for ph_idx in range(10):
        name = sim.PHASE_NAMES.get(ph_idx, "?")
        times = phase_times.get(ph_idx, [])
        if times:
            print(f"  {name:22s}  mean={np.mean(times):7.1f}  "
                  f"std={np.std(times):7.1f}  "
                  f"min={np.min(times):5d}  max={np.max(times):5d}")

    # Write results to JSON
    results_path = Path(model_path).parent / "eval_results.json"
    import json
    results = {
        "model": str(model_path),
        "episodes": n_episodes,
        "full_cycles": full_cycles,
        "completion_rate_pct": round(completion_rate, 2),
        "timeouts": timeouts,
        "avg_reward": round(float(np.mean(rewards_list)), 1),
        "std_reward": round(float(np.std(rewards_list)), 1),
        "avg_length": round(float(np.mean(lengths_list)), 0),
        "tolerances_mm": {
            "place": sim.PLACE_TOLERANCE * 1000,
            "clear": sim.CLEAR_TOLERANCE * 1000,
            "pickup": sim.PICKUP_TOLERANCE * 1000,
            "drop": sim.DROP_TOLERANCE * 1000,
        },
        "phase_entries": {sim.PHASE_NAMES[k]: v
                         for k, v in phase_entries.items()},
        "phase_conversions": {},
    }
    for ph_idx in range(9):
        curr = phase_entries.get(ph_idx, 0)
        nxt  = phase_entries.get(ph_idx + 1, 0)
        if curr > 0:
            key = f"{sim.PHASE_NAMES[ph_idx]}->{sim.PHASE_NAMES[ph_idx+1]}"
            results["phase_conversions"][key] = round(nxt / curr * 100, 1)

    results_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved: {results_path}")

    return completion_rate


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NEXUS Arm Policy Evaluator")
    parser.add_argument("--model", type=str, default=None,
                        help="Path to model .zip (default: latest final)")
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()

    if args.model:
        model_path = Path(args.model)
    else:
        # Auto-detect: prefer final, else latest checkpoint
        ckpt_dir = Path(r"E:\NEXUS_V2_RECREATED\training\arm_checkpoints_urdf")
        final = ckpt_dir / "nexus_arm_urdf_final.zip"
        if final.exists():
            model_path = final
        else:
            zips = sorted(ckpt_dir.glob("nexus_arm_urdf_*_steps.zip"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
            if not zips:
                print("No checkpoints found")
                sys.exit(1)
            model_path = zips[0]

    if not model_path.exists():
        print(f"Model not found: {model_path}")
        sys.exit(1)

    run_eval(model_path, args.episodes, args.render)
