# 皮皮 · 桌面宠物猫

一只**逼真写实**的银虎斑美短桌面宠物猫，名字叫 **皮皮**。
基于真实照片生成各姿势精灵图，用 PySide6 渲染成无边框、半透明、置顶的桌面小窗。

## 特性

- **逼真不卡通**：精灵图由真实照片经 AI 生成，写实质感；银灰底色 + 深灰黑虎斑纹，白口鼻白爪，粉鼻头黄绿眼。
- **12 种姿势**：idle 端坐 / lie_down 趴卧 / roll 仰躺打滚 / sleep 睡觉 / happy 开心 / head_tilt 歪头 / beg 讨饭 / shake 踱步 / play_ball 玩线球 / yawn 伸懒腰 / eating 吃饭 / grooming 舔毛。
- **猫系互动**：点击 → 随机反应（喵叫/打滚/歪头/舔毛）+ 台词气泡；双击挠肚皮；长按抚摸会打呼噜。
- **久坐提醒**：45 分钟久坐 + 3 分钟活动环形倒计时（快到点变橙色警示）；到点置顶弹窗，60 秒不处理自动「稍后 5 分钟」；点击身边的小圆环打开设置面板；电脑闲置超 10 分钟视为已起身自动重新计时；「我已起身」后进入休息倒计时并统计今日/累计起身次数；设置自动保存。
- **定时提醒**：托盘菜单「定时提醒」可自定义提醒时间（HH:MM）和内容，每天到点以气泡 + 系统通知提醒，重启后依然保留。
- **可拖动 · 托盘菜单**：左键拖动移动位置；托盘菜单可互动/打滚/睡觉/打开久坐提醒设置/退出。

## 快速使用（两种方式）

### 方式一：打包成 EXE，点开即用（推荐）

在 **Windows** 电脑上，把本工程文件夹整个拷过去，双击：

```
build_exe.bat
```

脚本会自动安装依赖并用 PyInstaller 打包，完成后在 `dist\pipi_pet.exe` 生成单文件 EXE，双击即可运行（无需 Python 环境）。

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
| 左键点击皮皮 | 随机互动反应（喵叫/打滚/歪头/舔毛） |
| 左键按住拖动 | 移动皮皮位置 |
| 双击 | 挠肚皮（仰躺打滚） |
| 长按 | 抚摸（歪头 + 呼噜） |
| 右键 | 弹出菜单 |
| 托盘图标左键 | 互动 |
| 托盘右键菜单 | 陪我玩 / 打滚撒娇 / 舔毛毛 / 讨饭饭 / 伸懒腰 / 去睡觉 / 定时提醒 / 久坐提醒设置 / 退出 |
| 键盘快捷键 | 空格=打招呼　R=打滚　S=睡觉　F=讨饭　H=舔毛　Y=伸懒腰　E=吃饭 |

闲置约 2 分钟后皮皮会自动趴下睡觉；久坐提醒按设定的节奏工作；各姿势精灵图已按主体占比做视觉归一，切换姿势时皮皮大小保持一致。

## 测试

测试文件统一以 **UIH** 为前缀：

```bash
pip install pytest
pytest
```

包含：
- `tests/UIH_test_config.py` — 名字/有尾/逼真/姿势齐备/精灵图存在
- `tests/UIH_test_fsm.py` — 状态机/互动/心情/时间感知
- `tests/UIH_test_reminder.py` — 久坐提醒
- `tests/UIH_test_timed_reminder.py` — 定时提醒：增删/覆盖/到点触发/每天一次/追补窗口/持久化/容错

## 工程结构

```
pipi_pet_project/
├─ main.py                 # 启动入口
├─ biscuit_pet/
│  ├─ __init__.py
│  ├─ core.py              # 可测试的核心逻辑（状态机/提醒，无 Qt 依赖）
│  ├─ app.py               # PySide6 界面层
│  └─ sprites/             # 13 张姿势精灵图（透明 PNG）+ icon.ico
├─ tests/                  # UIH 前缀测试
├─ requirements.txt
├─ build_exe.bat           # 一键打包 EXE（pipi_pet.exe）
├─ run.bat                 # 直接运行
└─ pytest.ini
```

## 自动化打包（GitHub Actions）

仓库已配置 `.github/workflows/build-exe.yml`：每次推送到 `main`（或手动 **Actions → Run workflow**）会自动：
1. 在 Ubuntu 上跑全部 **UIH 前缀测试**；
2. 测试通过后在 **Windows runner** 上用 PyInstaller 打包；
3. 把 `pipi_pet.exe` 作为产物（Artifact）上传到该次运行，**点进 Actions 对应运行即可下载**，无需本地装环境。

## 说明

- EXE 必须在 **Windows** 上生成（PyInstaller 不支持跨平台打包）；本地手动打包用 `build_exe.bat`，云端自动打包走 GitHub Actions。打包后均为单文件、点开即用。
- 精灵图由 AI 基于真实照片生成，已做绿幕抠图、边缘去色与水印清理。
