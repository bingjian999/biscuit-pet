# 饼干 · 桌面宠物狗

一只**逼真写实**的桌面宠物狗，名字叫 **饼干**，**没有尾巴**。
基于上传的真实照片生成各姿势精灵图，用 PySide6 渲染成无边框、半透明、置顶的桌面小窗。

## 特性

- **逼真不卡通**：精灵图由真实照片经 AI 生成，写实质感。
- **没有尾巴**：饼干天然无尾，所有姿势均无尾巴。
- **打滚撒娇**：自发或点击时仰躺打滚、伸舌笑。
- **大眼睛注视**：偶尔回到正面，圆眼睛深情望着你。
- **提醒主人动一动**：每 30 分钟弹出气泡提醒久坐起身活动（可关闭/推迟）。
- **点击互动**：左键点击 → 随机反应（汪叫/打滚/注视）+ 台词气泡。
- **各种姿势**：idle 端坐 / lie_down 趴着 / stare 注视 / roll 打滚 / sleep 睡觉 / happy 开心，共 6 种。
- **可拖动 · 托盘菜单**：左键拖动移动位置；托盘菜单可互动/打滚/睡觉/立刻提醒/退出。

## 快速使用（两种方式）

### 方式一：打包成 EXE，点开即用（推荐）

在 **Windows** 电脑上，把本工程文件夹整个拷过去，双击：

```
build_exe.bat
```

脚本会自动安装依赖并用 PyInstaller 打包，完成后在 `dist\biscuit_pet.exe` 生成单文件 EXE，双击即可运行（无需 Python 环境）。

### 方式二：直接用 Python 运行

已装 Python 3.9+ 的机器上双击：

```
run.bat
```

或手动：

```bash
pip install -r requirements.txt
python main.py
```

## 操作说明

| 操作 | 效果 |
|---|---|
| 左键点击饼干 | 随机互动反应（汪叫/打滚/注视） |
| 左键按住拖动 | 移动饼干位置 |
| 右键 | 弹出菜单 |
| 托盘图标左键 | 互动 |
| 托盘右键菜单 | 陪我玩 / 打滚撒娇 / 去睡觉 / 立刻提醒我动一动 / 退出 |

闲置约 2 分钟后饼干会自动趴下睡觉；每 30 分钟会提醒主人起来动一动。

## 测试

测试文件统一以 **UIH** 为前缀：

```bash
pip install pytest
pytest
```

包含：
- `tests/UIH_test_config.py` — 名字/无尾/逼真/姿势齐备/精灵图存在
- `tests/UIH_test_fsm.py` — 状态机：互动/打滚到期/久睡/注视切换
- `tests/UIH_test_reminder.py` — 久坐提醒：到点触发/重排/关闭/推迟

## 工程结构

```
biscuit_pet_project/
├─ main.py                 # 启动入口
├─ biscuit_pet/
│  ├─ __init__.py
│  ├─ core.py              # 可测试的核心逻辑（状态机/提醒，无 Qt 依赖）
│  ├─ app.py                # PySide6 界面层
│  └─ sprites/             # 6 张逼真无尾姿势精灵图（透明 PNG）
│     ├─ idle.png  lie_down.png  stare.png
│     └─ roll.png  sleep.png     happy.png
├─ tests/                  # UIH 前缀测试
├─ requirements.txt
├─ build_exe.bat           # 一键打包 EXE
├─ run.bat                 # 直接运行
└─ pytest.ini
```

## 自动化打包（GitHub Actions）

仓库已配置 `.github/workflows/build-exe.yml`：每次推送到 `main`（或手动 **Actions → Run workflow**）会自动：
1. 在 Ubuntu 上跑全部 **UIH 前缀测试**；
2. 测试通过后在 **Windows runner** 上用 PyInstaller 打包；
3. 把 `biscuit_pet.exe` 作为产物（Artifact）上传到该次运行，**点进 Actions 对应运行即可下载**，无需本地装环境。

## 说明

- EXE 必须在 **Windows** 上生成（PyInstaller 不支持跨平台打包）；本地手动打包用 `build_exe.bat`，云端自动打包走 GitHub Actions。打包后均为单文件、点开即用。
- 精灵图含「由 AI 生成」水印（已在角点尽量裁除）。
