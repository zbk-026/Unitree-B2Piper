#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/home/linux/anaconda3/envs/env_isaaclab/bin/python}"
LOCAL_ASSET_ROOT="${REPO_ROOT}/atec_robot_model"
WORKSPACE_ASSET_ROOT="/home/linux/ATEC_taska/atec_robot_model"

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Python interpreter not found or not executable: ${PYTHON_BIN}" >&2
    exit 2
fi

if [[ -n "${TASKA_ASSET_ROOT:-}" ]]; then
    ASSET_ROOT="${TASKA_ASSET_ROOT}"
elif [[ -d "${LOCAL_ASSET_ROOT}" ]]; then
    ASSET_ROOT="${LOCAL_ASSET_ROOT}"
elif [[ -d "${WORKSPACE_ASSET_ROOT}" ]]; then
    ASSET_ROOT="${WORKSPACE_ASSET_ROOT}"
else
    echo "Task A external assets were not found." >&2
    echo "Clone atec_robot_model into ${LOCAL_ASSET_ROOT}, or set TASKA_ASSET_ROOT." >&2
    exit 2
fi

required_assets=(
    "robot/b2/b2_piper.usda"
    "scene/kloofendal_43d_clear_puresky_4k.hdr"
    "scene/TilesMarbleSpiderWhiteBrickBondHoned.mdl"
)
for relative_path in "${required_assets[@]}"; do
    if [[ ! -f "${ASSET_ROOT}/${relative_path}" ]]; then
        echo "Task A external asset is missing: ${ASSET_ROOT}/${relative_path}" >&2
        echo "Set TASKA_ASSET_ROOT to a complete atec_robot_model checkout." >&2
        exit 2
    fi
done

export TASKA_ASSET_ROOT="${ASSET_ROOT}"
cd "${REPO_ROOT}"
exec "${PYTHON_BIN}" scripts/evaluate_front.py "$@"
