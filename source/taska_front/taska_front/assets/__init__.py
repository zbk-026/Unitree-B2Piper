import os
from pathlib import Path


_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_ASSET_ROOT = _REPOSITORY_ROOT / "atec_robot_model"
ATEC_ASSETS_MODEL_DIR = str(Path(os.environ.get("TASKA_ASSET_ROOT", _DEFAULT_ASSET_ROOT)).expanduser().resolve())
_REQUIRED_TASK_A_ASSETS = (
    "robot/b2/b2_piper.usda",
    "scene/kloofendal_43d_clear_puresky_4k.hdr",
    "scene/TilesMarbleSpiderWhiteBrickBondHoned.mdl",
)


def require_task_a_assets() -> Path:
    """Validate the external model assets before constructing the Isaac scene."""
    asset_root = Path(ATEC_ASSETS_MODEL_DIR)
    missing = [relative_path for relative_path in _REQUIRED_TASK_A_ASSETS if not (asset_root / relative_path).is_file()]
    if missing:
        missing_text = ", ".join(missing)
        raise FileNotFoundError(
            f"Task A external assets are incomplete at: {asset_root}. Missing: {missing_text}. "
            "Clone atec_robot_model into this repository as ./atec_robot_model, or set "
            "TASKA_ASSET_ROOT to the directory that contains robot/ and scene/."
        )
    return asset_root
