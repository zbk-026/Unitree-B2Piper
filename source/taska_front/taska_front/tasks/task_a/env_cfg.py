"""B2Piper configuration for the fixed Task A front-route demo."""

from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.utils import configclass

from taska_front.assets.robots import UNITREE_B2_PIPER_CFG
from taska_front.tasks.task_base import BaseEnvCfg, TerminationsCfg
from taska_front.tasks.task_a import mdp as task_a_mdp

from .terrain import TASK_A_FRONT_TERRAIN_CFG


@configclass
class TaskAFrontTerminationsCfg(TerminationsCfg):
    reach_goal_x = DoneTerm(
        func=task_a_mdp.robot_x_greater_than,
        params={"asset_cfg": SceneEntityCfg("robot"), "x_threshold": 55.0},
        time_out=False,
    )


@configclass
class TaskAFrontRewardsCfg:
    progress_reward = RewTerm(
        func=task_a_mdp.CrossXMulti,
        params={
            "asset_cfg": SceneEntityCfg("robot"),
            "x_thresholds": [-115.0, -35.0, 45.0, 55.0],
            "rewards": [2.0, 4.0, 8.0, 1.0],
            "debug": False,
            "visual_assets": False,
        },
        weight=1.0,
    )


@configclass
class TaskAFrontB2Cfg(BaseEnvCfg):
    """Official B2Piper dynamics and front terrain, with no stair terrain."""

    def __post_init__(self):
        self.scene.robot = UNITREE_B2_PIPER_CFG.replace(
            prim_path="{ENV_REGEX_NS}/Robot",
            init_state=UNITREE_B2_PIPER_CFG.init_state.replace(pos=(-141.0, 0.0, 0.58)),
        )
        super().__post_init__()

        self.scene.terrain = TASK_A_FRONT_TERRAIN_CFG
        self.sim.physics_material = self.scene.terrain.physics_material
        self.rewards = TaskAFrontRewardsCfg()
        self.terminations = TaskAFrontTerminationsCfg()

        # The demo uses only the exact proprioceptive interface consumed by policy.pt.
        self.observations.proprio.enable_corruption = False
        self.events.physics_material = None
        self.events.base_external_force_torque = None
        self.terminations.fall.params["minimum_height"] = -20.0
        self.terminations.illegal_contact.params["sensor_cfg"].body_names = [
            UNITREE_B2_PIPER_CFG.base_link_name,
            ".*_hip",
            ".*_thigh",
        ]

        joint_names = UNITREE_B2_PIPER_CFG.joint_names
        self.observations.proprio.joint_pos.params["asset_cfg"].joint_names = joint_names
        self.observations.proprio.joint_vel.params["asset_cfg"].joint_names = joint_names
        self.actions.joint_leg.joint_names = UNITREE_B2_PIPER_CFG.leg_joint_names
        self.actions.joint_arm.joint_names = UNITREE_B2_PIPER_CFG.arm_joint_names
        self.actions.joint_wheel = None
