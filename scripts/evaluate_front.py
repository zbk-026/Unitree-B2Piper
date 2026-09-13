#!/usr/bin/env python3
"""Run the validated 48-D B2Piper policy on the Task A front route."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import traceback
from pathlib import Path

from isaaclab.app import AppLauncher


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_OBSERVATION_DIM = 48
POLICY_ACTION_DIM = 12
OFFICIAL_ACTION_DIM = 20
POLICY_SHA256 = "18ef72c72329016b7c9a0c5c85b980720ae80027ca874b29c6632c61583c5705"
START_X = -141.0
TARGET_X = 55.0
CENTERLINE_GAINS = {
    "lateral_position_gain": 0.12,
    "lateral_velocity_gain": 0.30,
    "cross_track_heading_gain": 0.08,
    "max_desired_heading": 0.30,
    "heading_gain": 1.50,
    "yaw_rate_gain": 0.10,
    "max_lateral_speed": 0.40,
    "max_yaw_rate": 0.40,
}
COMMAND_PHASES = (
    (None, 2.0, "initial_flat", 3.0),
    (2.0, 7.5, "rough_uphill_1", 1.5),
    (7.5, 9.5, "downhill_1", 1.0),
    (9.5, 11.5, "uphill_2", 1.5),
    (11.5, 13.5, "downhill_2", 1.0),
    (13.5, None, "front_exit", 1.5),
)
TELEMETRY_FIELDS = (
    "seed",
    "step",
    "elapsed_time",
    "score",
    "root_x",
    "relative_y",
    "world_vx",
    "world_vy",
    "body_vx",
    "body_vy",
    "tilt_rad",
    "phase",
    "command_vx",
    "command_vy",
    "command_yaw",
    "action_abs_max",
    "terminated",
    "truncated",
    "termination_reason",
)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--policy", type=Path, default=REPO_ROOT / "policy.pt")
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--max-steps", type=int, default=24000)
parser.add_argument("--lateral-limit", type=float, default=8.0)
parser.add_argument("--output-dir", type=Path, default=None)
parser.add_argument("--disable-fabric", action="store_true")
parser.add_argument("--no-camera-follow", action="store_true")
AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
sys.argv = [sys.argv[0], *hydra_args]
OUTPUT_DIR = (args_cli.output_dir or REPO_ROOT / "logs" / "front_eval" / f"seed_{args_cli.seed}").expanduser().resolve()
# AppLauncher consumes and removes launch arguments from args_cli in place.
GUI_CAMERA_FOLLOW_ENABLED = not args_cli.no_camera_follow and not args_cli.headless


def _write_status(stage: str, **details) -> None:
    """Persist the most recent startup or rollout stage for post-mortem diagnosis."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": stage, "seed": args_cli.seed, **details}
    (OUTPUT_DIR / "status.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _validate_inputs() -> tuple[Path, str]:
    if args_cli.max_steps <= 0:
        raise ValueError("--max-steps must be positive.")
    if args_cli.lateral_limit <= 0.0:
        raise ValueError("--lateral-limit must be positive.")
    policy_path = args_cli.policy.expanduser().resolve()
    if not policy_path.is_file():
        raise FileNotFoundError(f"Policy not found: {policy_path}")
    actual_hash = _policy_sha256(policy_path)
    if actual_hash != POLICY_SHA256:
        raise ValueError(f"Unexpected policy SHA-256: {actual_hash}; expected {POLICY_SHA256}.")
    from taska_front.assets import require_task_a_assets

    require_task_a_assets()
    return policy_path, actual_hash


def _policy_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as policy_file:
        for block in iter(lambda: policy_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def task_a_progress_score(max_x: float) -> float:
    """Official Task A score from historical maximum world X."""
    starts = (-141.0, -115.0, -35.0, 45.0, 125.0)
    ends = (-115.0, -35.0, 45.0, 125.0, 140.0)
    rewards = (2.0, 4.0, 8.0, 8.0, 4.0)
    return sum(
        max(0.0, min(1.0, (max_x - start) / (end - start))) * reward
        for start, end, reward in zip(starts, ends, rewards)
    )


def phase_at_score(score: float) -> tuple[str, float]:
    """Use the same score threshold epsilon as the existing evaluator."""
    coordinate = score + 1.0e-3
    for start, end, name, command_vx in COMMAND_PHASES:
        if (start is None or coordinate >= start) and (end is None or coordinate < end):
            return name, command_vx
    raise RuntimeError(f"No command phase contains score={score}.")


def build_policy_observation(proprio, command):
    """Adapt official 72-D proprioception to the policy's 48-D input order."""
    import torch

    if proprio.ndim != 2 or proprio.shape[1] != 72:
        raise ValueError(f"Expected official proprioception shape (N, 72), got {tuple(proprio.shape)}.")
    if command.ndim != 2 or command.shape != (proprio.shape[0], 3):
        raise ValueError(f"Expected command shape ({proprio.shape[0]}, 3), got {tuple(command.shape)}.")
    action_scale = torch.as_tensor(
        (0.25, 0.50, 0.50, 0.25, 0.50, 0.50, 0.25, 0.50, 0.50, 0.25, 0.50, 0.50),
        dtype=proprio.dtype,
        device=proprio.device,
    ).view(1, -1)
    observation = torch.cat(
        (
            proprio[:, 3:6] * 0.25,
            proprio[:, 9:12],
            command.to(dtype=proprio.dtype, device=proprio.device),
            proprio[:, 12:24],
            proprio[:, 32:44] * 0.05,
            proprio[:, 52:64] / action_scale,
            proprio[:, 0:3] * 2.0,
        ),
        dim=-1,
    )
    if observation.shape[1] != POLICY_OBSERVATION_DIM:
        raise RuntimeError(f"Constructed policy observation has shape {tuple(observation.shape)}.")
    return observation


def map_policy_action_to_official(action_train):
    """Map 12 leg actions to Task A's official 20-D B2Piper action space."""
    import torch

    if action_train.ndim == 1:
        action_train = action_train.unsqueeze(0)
    if action_train.ndim != 2 or action_train.shape[1] != POLICY_ACTION_DIM:
        raise ValueError(f"Expected policy action shape (N, 12), got {tuple(action_train.shape)}.")
    scale = torch.as_tensor(
        (0.25, 0.50, 0.50, 0.25, 0.50, 0.50, 0.25, 0.50, 0.50, 0.25, 0.50, 0.50),
        dtype=action_train.dtype,
        device=action_train.device,
    ).view(1, -1)
    official_action = torch.zeros(
        (action_train.shape[0], OFFICIAL_ACTION_DIM), dtype=action_train.dtype, device=action_train.device
    )
    official_action[:, :POLICY_ACTION_DIM] = torch.clamp(action_train, -100.0, 100.0) * scale
    return official_action


def centerline_command(robot, forward_speed: float, *, centerline_y: float = 0.0):
    """Generate the training-aligned forward, lateral, and yaw command."""
    import torch
    import isaaclab.utils.math as math_utils

    root_pos = robot.data.root_pos_w
    root_quat = robot.data.root_quat_w
    root_lin_vel_w = robot.data.root_lin_vel_w
    root_ang_vel_w = robot.data.root_ang_vel_w
    relative_y = root_pos[:, 1] - centerline_y
    forward_b = torch.zeros_like(root_pos)
    forward_b[:, 0] = 1.0
    forward_w = math_utils.quat_apply(root_quat, forward_b)
    heading = torch.atan2(forward_w[:, 1], forward_w[:, 0])
    desired_heading = torch.clamp(
        -CENTERLINE_GAINS["cross_track_heading_gain"] * relative_y,
        -CENTERLINE_GAINS["max_desired_heading"],
        CENTERLINE_GAINS["max_desired_heading"],
    )
    heading_error = torch.atan2(torch.sin(heading - desired_heading), torch.cos(heading - desired_heading))
    lateral = (
        -CENTERLINE_GAINS["lateral_position_gain"] * relative_y
        - CENTERLINE_GAINS["lateral_velocity_gain"] * root_lin_vel_w[:, 1]
    )
    yaw = (
        -CENTERLINE_GAINS["heading_gain"] * heading_error
        - CENTERLINE_GAINS["yaw_rate_gain"] * root_ang_vel_w[:, 2]
    )
    command = torch.zeros((root_pos.shape[0], 3), dtype=root_pos.dtype, device=root_pos.device)
    command[:, 0] = forward_speed
    command[:, 1] = torch.clamp(lateral, -CENTERLINE_GAINS["max_lateral_speed"], CENTERLINE_GAINS["max_lateral_speed"])
    command[:, 2] = torch.clamp(yaw, -CENTERLINE_GAINS["max_yaw_rate"], CENTERLINE_GAINS["max_yaw_rate"])
    return command


class CameraFollower:
    """Follow the robot from a fixed world-frame overhead angle.

    The previous camera offset was transformed by the robot quaternion.  Body
    pitch, roll, and yaw therefore rotated the viewport on every step.  This
    follower uses fixed world-frame offsets instead: only the camera target
    translates with the robot, while both eye and look-at points are smoothed
    independently to suppress gait and terrain-height bobbing.
    """

    EYE_OFFSET_WORLD = (-7.0, -6.0, 7.0)
    LOOKAT_OFFSET_WORLD = (2.0, 0.0, 0.8)
    SMOOTHING_ALPHA = 0.08

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self._eye = None
        self._lookat = None

    def update(self, env) -> None:
        if not self.enabled:
            return
        unwrapped = env.unwrapped
        controller = getattr(unwrapped, "viewport_camera_controller", None)
        if controller is None:
            return
        import torch

        robot = unwrapped.scene["robot"]
        robot_pos = robot.data.root_pos_w[0]
        eye_offset = torch.tensor(self.EYE_OFFSET_WORLD, dtype=robot_pos.dtype, device=robot_pos.device)
        lookat_offset = torch.tensor(self.LOOKAT_OFFSET_WORLD, dtype=robot_pos.dtype, device=robot_pos.device)
        target_eye = robot_pos + eye_offset
        target_lookat = robot_pos + lookat_offset
        target_eye[2] = torch.clamp(target_eye[2], min=1.0)
        target_lookat[2] = torch.clamp(target_lookat[2], min=0.2)
        alpha = self.SMOOTHING_ALPHA
        self._eye = target_eye.clone() if self._eye is None else (1.0 - alpha) * self._eye + alpha * target_eye
        self._lookat = (
            target_lookat.clone() if self._lookat is None else (1.0 - alpha) * self._lookat + alpha * target_lookat
        )
        controller.set_view_env_index(env_index=0)
        controller.update_view_location(
            eye=self._eye.detach().cpu().numpy(), lookat=self._lookat.detach().cpu().numpy()
        )


def _termination_reason(env) -> str:
    manager = getattr(env.unwrapped, "termination_manager", None)
    if manager is None:
        return ""
    active = []
    for name, values in manager.get_active_iterable_terms(0):
        if any(float(value) > 0.5 for value in values):
            active.append(name)
    return "|".join(active)


def _state(robot) -> dict[str, float]:
    import torch

    root_pos = robot.data.root_pos_w[0]
    world_velocity = robot.data.root_lin_vel_w[0]
    body_velocity = robot.data.root_lin_vel_b[0]
    gravity = robot.data.projected_gravity_b[0]
    tilt = torch.acos(torch.clamp(-gravity[2], -1.0, 1.0))
    return {
        "root_x": float(root_pos[0].item()),
        "relative_y": float(root_pos[1].item()),
        "world_vx": float(world_velocity[0].item()),
        "world_vy": float(world_velocity[1].item()),
        "body_vx": float(body_velocity[0].item()),
        "body_vy": float(body_velocity[1].item()),
        "tilt_rad": float(tilt.item()),
    }


def main(simulation_app, policy_path: Path, actual_hash: str) -> None:
    import gymnasium as gym
    import torch

    _write_status("creating_environment_config")
    import taska_front.tasks  # noqa: F401
    from taska_front.tasks.task_a import TaskAFrontB2Cfg
    from taska_front.tasks.task_base import BetterTerrainGenerator

    torch.manual_seed(args_cli.seed)
    env_cfg = TaskAFrontB2Cfg()
    env_cfg.seed = args_cli.seed
    env_cfg.scene.num_envs = 1
    env_cfg.scene.env_spacing = 2.5
    env_cfg.sim.device = args_cli.device
    env_cfg.sim.use_fabric = not args_cli.disable_fabric
    env_cfg.scene.robot.init_state.pos = (START_X, 0.0, 0.58)
    env_cfg.observations.extero = None
    env_cfg.observations.image = None
    env_cfg.scene.lidar_sensor = None
    env_cfg.scene.head_camera = None
    env_cfg.scene.ee_camera = None
    env_cfg.scene.ee_dual_camera = None

    # BetterTerrainGenerator owns a class-level cursor. Reset it before each run
    # so the ten official front tiles always occupy the same world coordinates.
    BetterTerrainGenerator._cell_counter = 0
    BetterTerrainGenerator.sub_terrain_types = []
    _write_status("creating_environment")
    env = gym.make("TaskAFront-B2Piper-v0", cfg=env_cfg)
    _write_status("environment_created")

    telemetry_path = OUTPUT_DIR / "telemetry.csv"
    summary_path = OUTPUT_DIR / "summary.json"
    try:
        _write_status("resetting_environment")
        obs, _ = env.reset()
        _write_status("environment_reset")
        if "proprio" not in obs or tuple(obs["proprio"].shape) != (1, 72):
            raise ValueError(f"Expected official proprioception shape (1, 72), got {tuple(obs.get('proprio', ()).shape)}.")
        if int(env.action_space.shape[-1]) != OFFICIAL_ACTION_DIM:
            raise ValueError(f"Expected official action dimension 20, got {env.action_space.shape[-1]}.")

        robot = env.unwrapped.scene["robot"]
        policy = torch.jit.load(str(policy_path), map_location=env.unwrapped.device)
        policy.eval()
        _write_status("policy_loaded")
        _, probe_speed = phase_at_score(task_a_progress_score(START_X))
        probe_action = policy(build_policy_observation(obs["proprio"], centerline_command(robot, probe_speed)))
        if tuple(probe_action.shape) != (1, POLICY_ACTION_DIM) or not torch.isfinite(probe_action).all():
            raise ValueError("policy.pt is not a finite 48-D-to-12-D TorchScript policy.")

        max_x = START_X
        max_abs_y = 0.0
        max_tilt = 0.0
        max_action_abs = 0.0
        total_environment_reward = 0.0
        reached_target = False
        termination_reason = "max_steps"
        steps = 0
        phase_samples = {name: [] for _, _, name, _ in COMMAND_PHASES}
        follower = CameraFollower(enabled=GUI_CAMERA_FOLLOW_ENABLED)
        step_dt = float(env.unwrapped.step_dt)

        _write_status("rollout_started")
        with telemetry_path.open("w", newline="", encoding="utf-8") as telemetry_file:
            telemetry_writer = csv.DictWriter(telemetry_file, fieldnames=TELEMETRY_FIELDS)
            telemetry_writer.writeheader()
            for step in range(args_cli.max_steps):
                if not simulation_app.is_running():
                    if step == 0:
                        raise RuntimeError("Isaac Sim stopped before the first rollout step.")
                    termination_reason = "simulator_closed"
                    break
                follower.update(env)
                state = _state(robot)
                max_x = max(max_x, state["root_x"])
                score = task_a_progress_score(max_x)
                max_abs_y = max(max_abs_y, abs(state["relative_y"]))
                max_tilt = max(max_tilt, state["tilt_rad"])
                if max_x >= TARGET_X:
                    reached_target = True
                    termination_reason = "target_x"
                    break
                if abs(state["relative_y"]) >= args_cli.lateral_limit:
                    termination_reason = "lateral_limit"
                    break

                phase_name, forward_speed = phase_at_score(score)
                command = centerline_command(robot, forward_speed)
                policy_observation = build_policy_observation(obs["proprio"], command)
                with torch.inference_mode():
                    action_train = policy(policy_observation)
                if not torch.isfinite(action_train).all():
                    raise RuntimeError(f"Policy produced non-finite actions at step {step}.")
                max_action_abs = max(max_action_abs, float(action_train.abs().max().item()))
                action_official = map_policy_action_to_official(action_train)
                obs, reward, terminated, truncated, _ = env.step(action_official)
                steps += 1
                phase_samples[phase_name].append(state["world_vx"])
                done = bool(torch.as_tensor(terminated).any().item() or torch.as_tensor(truncated).any().item())
                current_reason = _termination_reason(env) if done else ""
                total_environment_reward += float(torch.as_tensor(reward).mean().item())
                telemetry_writer.writerow(
                    {
                        "seed": args_cli.seed,
                        "step": step,
                        "elapsed_time": steps * step_dt,
                        "score": score,
                        **state,
                        "phase": phase_name,
                        "command_vx": float(command[0, 0].item()),
                        "command_vy": float(command[0, 1].item()),
                        "command_yaw": float(command[0, 2].item()),
                        "action_abs_max": float(action_train.abs().max().item()),
                        "terminated": bool(torch.as_tensor(terminated).any().item()),
                        "truncated": bool(torch.as_tensor(truncated).any().item()),
                        "termination_reason": current_reason,
                    }
                )
                if done:
                    post_step_x = float(robot.data.root_pos_w[0, 0].item())
                    max_x = max(max_x, post_step_x)
                    reached_target = max_x >= TARGET_X
                    termination_reason = "target_x" if reached_target else (current_reason or "done")
                    break

        summary = {
            "task": "TaskAFront-B2Piper-v0",
            "route": {"start_x": START_X, "target_x": TARGET_X, "target_score": task_a_progress_score(TARGET_X)},
            "terrain": "official Task A rows 1-10; rows 11-15 are flat; no stairs",
            "seed": args_cli.seed,
            "policy": str(policy_path),
            "policy_sha256": actual_hash,
            "policy_observation_dim": POLICY_OBSERVATION_DIM,
            "policy_action_dim": POLICY_ACTION_DIM,
            "official_action_dim": OFFICIAL_ACTION_DIM,
            "command_phases": [
                {"start_score": start, "end_score": end, "name": name, "command_vx": speed}
                for start, end, name, speed in COMMAND_PHASES
            ],
            "camera_follow": GUI_CAMERA_FOLLOW_ENABLED,
            "score": task_a_progress_score(max_x),
            "max_x": max_x,
            "max_abs_y": max_abs_y,
            "max_tilt_rad": max_tilt,
            "max_action_abs": max_action_abs,
            "environment_score": total_environment_reward,
            "steps": steps,
            "elapsed_time": steps * step_dt,
            "termination_reason": termination_reason,
            "reached_target": reached_target,
            "phase_mean_world_vx": {
                name: (sum(samples) / len(samples) if samples else None)
                for name, samples in phase_samples.items()
            },
        }
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        _write_status("completed", summary=str(summary_path), termination_reason=termination_reason)
        print(json.dumps(summary, indent=2), flush=True)
    finally:
        env.close()


if __name__ == "__main__":
    simulation_app = None
    try:
        _write_status("validating_inputs")
        policy_path, actual_hash = _validate_inputs()
        _write_status("launching_app")
        app_launcher = AppLauncher(args_cli)
        simulation_app = app_launcher.app
        _write_status("app_launched")
        main(simulation_app, policy_path, actual_hash)
    except BaseException as error:
        _write_status("failed", error_type=type(error).__name__, error_message=str(error))
        traceback.print_exc()
        raise
    finally:
        if simulation_app is not None:
            simulation_app.close()
