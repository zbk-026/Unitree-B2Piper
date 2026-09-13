import gymnasium as gym

gym.register(
    id="TaskAFront-B2Piper-v0",
    entry_point="taska_front.tasks.task_base.envs_base:BaseRLEnv",
    disable_env_checker=True,
    kwargs={"env_cfg_entry_point": f"{__name__}.env_cfg:TaskAFrontB2Cfg"},
)

from .env_cfg import TaskAFrontB2Cfg

__all__ = ["TaskAFrontB2Cfg"]
