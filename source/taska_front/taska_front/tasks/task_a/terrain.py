"""Fixed Task A front route: official pre-stairs terrain and flat exit."""

import isaaclab.sim as sim_utils
import isaaclab.terrains as terrain_gen
from isaaclab.terrains import TerrainImporterCfg

from taska_front.assets import ATEC_ASSETS_MODEL_DIR
from taska_front.tasks.task_base import BetterTerrainGenerator, BetterTerrainGeneratorCfg, BetterTerrainImporter


# The first ten rows are the official Task A front route. Rows 11--15 replace
# the official stair section with flat terrain so the demo ends at X=55.
FRONT_TERRAIN_SEQUENCE = (
    "flat",
    "flat",
    "random_rough",
    "random_rough",
    "random_rough",
    "random_rough",
    "hf_pyramid_slope",
    "hf_pyramid_slope_inv",
    "hf_pyramid_slope",
    "hf_pyramid_slope_inv",
    "flat",
    "flat",
    "flat",
    "flat",
    "flat",
)

TASK_A_FRONT_TERRAIN_CFG = TerrainImporterCfg(
    class_type=BetterTerrainImporter,
    prim_path="/World/ground",
    terrain_type="generator",
    terrain_generator=BetterTerrainGeneratorCfg(
        class_type=BetterTerrainGenerator,
        seed=0,
        size=(20.0, 20.0),
        border_width=0.0,
        num_rows=15,
        num_cols=1,
        horizontal_scale=0.1,
        vertical_scale=0.005,
        slope_threshold=0.75,
        use_cache=False,
        terrain_sequence=list(FRONT_TERRAIN_SEQUENCE),
        sub_terrains={
            "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=0.1),
            "random_rough": terrain_gen.HfRandomUniformTerrainCfg(
                proportion=0.1, noise_range=(0.02, 0.10), noise_step=0.02, border_width=0.25
            ),
            "hf_pyramid_slope": terrain_gen.HfPyramidSlopedTerrainCfg(
                proportion=0.2, slope_range=(0.39, 0.40), platform_width=2.5, border_width=0.25
            ),
            "hf_pyramid_slope_inv": terrain_gen.HfInvertedPyramidSlopedTerrainCfg(
                proportion=0.2, slope_range=(0.39, 0.40), platform_width=2.5, border_width=0.25
            ),
        },
    ),
    max_init_terrain_level=0,
    collision_group=-1,
    physics_material=sim_utils.RigidBodyMaterialCfg(
        friction_combine_mode="multiply",
        restitution_combine_mode="multiply",
        static_friction=1.0,
        dynamic_friction=1.0,
        restitution=1.0,
    ),
    visual_material=sim_utils.MdlFileCfg(
        mdl_path=f"{ATEC_ASSETS_MODEL_DIR}/scene/TilesMarbleSpiderWhiteBrickBondHoned.mdl",
        project_uvw=True,
        texture_scale=(0.25, 0.25),
    ),
    debug_vis=False,
)
