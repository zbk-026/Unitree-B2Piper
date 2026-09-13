# Task A B2Piper Front-Route Inference

## 环境配置

本 demo 基于 Isaac Lab `v2.3.2`，使用 `env_isaaclab` Python 环境和 NVIDIA GPU。

先按照官方 [Isaac Lab 安装指南](https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/pip_installation.html) 配置 Isaac Sim/Isaac Lab，然后安装本仓库的环境扩展：

```bash
git clone git@github.com:zbk-026/Unitree-B2Piper.git taska
cd taska

conda activate env_isaaclab
pip install -e source/taska_front
```

## 机器人下载

机器人 USD 和 Task A 场景资源不包含在本仓库中，需要使用 Git LFS 下载到仓库根目录：

```bash
cd taska
git clone <MODEL_REPOSITORY_URL> atec_robot_model
cd atec_robot_model
git lfs pull
cd ..
```

下载完成后，应存在以下文件：

```text
atec_robot_model/robot/b2/b2_piper.usda
atec_robot_model/scene/kloofendal_43d_clear_puresky_4k.hdr
atec_robot_model/scene/TilesMarbleSpiderWhiteBrickBondHoned.mdl
```

如果资源放在其他位置，可在运行前指定资源根目录：

```bash
export TASKA_ASSET_ROOT=/path/to/atec_robot_model
```

## 运行命令

激活 `env_isaaclab` 后，在仓库根目录运行：

```bash
bash scripts/run_front.sh
```

该命令启动 Isaac Sim GUI，使用固定世界坐标的机器人上方视角，并评估官方前置路线 `X=-141..55`。前十个官方地形 tile 保留平地、rough 和连续上下坡，后五个 tile 替换为平地，不包含楼梯。评估结果写入 `logs/front_eval/`。

无 GUI 运行：

```bash
bash scripts/run_front.sh --headless
```

可通过 `--no-camera-follow` 关闭镜头跟随：

```bash
bash scripts/run_front.sh --no-camera-follow
```
