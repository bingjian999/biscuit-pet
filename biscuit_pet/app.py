"""饼干桌面宠物 · Qt 界面层 v2。

新增互动：双击挠肚皮、长按抚摸、键盘快捷键、喂食、开机问候、心情显示。
"""

import os
import sys
import time
import datetime

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPixmap, QFont, QCursor, QIcon, QColor, QPainter, QPen, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
    QSystemTrayIcon,
    QMenu,
)

from .core import (
    PetConfig, PetFSM, ReminderScheduler,
    POSES, STATE_TO_POSE, STATE_DURATION,
    greeting_message,
)

SPRITE_DIR = os.path.join(os.path.dirname(__file__), "sprites")
PET_W, PET_H = 190, 280


def _sprite_path(pose):
    return os.path.join(SPRITE_DIR, f"{pose}.png")


class SpeechBubble(QWidget):
    """小狗头上的圆角台词气泡，自动消失。"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "background: rgba(255,255,255,235);"
            "border-radius: 16px;"
            "padding: 10px 18px;"
            "color:#5a3a1a;"
            "border: 1px solid rgba(200,170,120,180);"
        )
        self.label.setFont(QFont("Microsoft YaHei", 10))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text, top_left, duration=4200):
        self.label.setText(text)
        self.label.adjustSize()
        w, h = self.label.width() + 4, self.label.height() + 4
        self.resize(w, h)
        self.label.setGeometry(0, 0, w, h)
        self.move(top_left)
        self.show()
        self.raise_()
        self._timer.start(duration)


class PetWindow(QWidget):
    def __init__(self, config=None):
        super().__init__()
        self.config = config or PetConfig()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(PET_W, PET_H)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setGeometry(0, 0, PET_W, PET_H)

        self.sprites = {}
        for p in POSES:
            pix = QPixmap(_sprite_path(p))
            self.sprites[p] = pix

        self.fsm = PetFSM(
            self.config,
            time_fn=time.time,
            hour_fn=lambda: datetime.datetime.now().hour,
        )
        self.reminder = ReminderScheduler(self.config, time_fn=time.time)
        self.bubble = SpeechBubble()

        self._drag_offset = None
        self._press_time = 0.0
        self._press_pos = None
        self._dragged = False
        self._cur_pose = None
        self.set_pose("idle")

        # 状态机推进
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.on_tick)
        self.tick_timer.start(900)

        # 久坐提醒检查
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self.on_reminder_check)
        self.reminder_timer.start(60000)

        # 随机自发行为（每 2~5 分钟）
        self.romp_timer = QTimer(self)
        self.romp_timer.setSingleShot(True)
        self.romp_timer.timeout.connect(self.on_romp)
        self.romp_timer.start(120000)

        # 长按检测定时器（800ms → 抚摸）
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._on_hold)

        # 心情显示定时器（每 30 秒更新托盘 tooltip）
        self._mood_timer = QTimer(self)
        self._mood_timer.timeout.connect(self._update_mood_tooltip)
        self._mood_timer.start(30000)

        self._setup_tray()
        self._setup_shortcuts()
        self._place_bottom_right()
        self.show()

        # 开机问候
        QTimer.singleShot(800, self._greeting)

    # ---- 显示 ----
    def set_pose(self, pose):
        if pose == self._cur_pose:
            return
        self._cur_pose = pose
        pix = self.sprites.get(pose)
        if pix is None or pix.isNull():
            return
        self.label.setPixmap(
            pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    # ---- 状态机 / 提醒 ----
    def on_tick(self):
        state, changed = self.fsm.tick()
        if changed:
            self.set_pose(self.fsm.pose())

    def on_reminder_check(self):
        due, msg = self.reminder.check()
        if due:
            self.set_pose("happy")
            self.show_bubble(msg)

    def on_romp(self):
        """自发行为：根据时间和心情选择状态。"""
        # 心情高 → 活泼行为；心情低 → 更可能 yawn/sleep
        if self.fsm.mood < 25:
            state = "yawn"
            speech = self.fsm.speech("yawn")
        else:
            state = self.fsm.time_aware_state()
            speech = self.fsm.speech(state)
        now = time.time()
        self.fsm.state = state
        self.fsm.last_interaction = now
        self.fsm.state_until = now + STATE_DURATION.get(state, 3.0)
        if state == "roll":
            self.fsm.roll_until = self.fsm.state_until
        elif state == "happy":
            self.fsm.happy_until = self.fsm.state_until
        self.set_pose(state)
        self.show_bubble(speech)
        import random
        self.romp_timer.start(int(random.uniform(120, 300)) * 1000)

    # ---- 交互 ----
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press_time = time.time()
            self._press_pos = e.globalPosition().toPoint()
            self._dragged = False
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            # 启动长按检测
            self._hold_timer.start(800)

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and (e.buttons() & Qt.LeftButton):
            # 移动超过 5px 算拖动，取消长按
            if (e.globalPosition().toPoint() - self._press_pos).manhattanLength() > 5:
                self._dragged = True
                self._hold_timer.stop()
            self.move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, e):
        self._hold_timer.stop()
        if not self._dragged and self._press_time > 0:
            # 短按 → 单击互动（延迟到 release 判断是否拖动）
            pass
        self._drag_offset = None
        self._press_time = 0.0

    def mouseDoubleClickEvent(self, e):
        """双击 → 挠肚皮。"""
        if e.button() == Qt.LeftButton:
            self._hold_timer.stop()
            state, speech = self.fsm.on_double_click()
            self.set_pose(state)
            self.show_bubble(speech)

    def _on_hold(self):
        """长按 800ms → 抚摸。"""
        if not self._dragged:
            state, speech = self.fsm.on_pet()
            self.set_pose(state)
            self.show_bubble(speech)

    def contextMenuEvent(self, e):
        self._hold_timer.stop()
        # 更新动态菜单项
        self._act_mood.setText(f"心情：{self.fsm.mood_label()}({self.fsm.mood})")
        self._act_stats.setText(f"互动次数：{self.fsm.interaction_count}")
        self._menu.exec(e.globalPos())

    # ---- 气泡 / 快捷键 / 托盘 ----
    def show_bubble(self, text, duration=4200):
        """在宠物头部上方显示台词气泡。"""
        if not text:
            return
        pt = self.mapToGlobal(QPoint(0, 0))
        bx = pt.x() + self.width() // 2 - 50
        by = pt.y() - 50
        self.bubble.show_message(text, QPoint(bx, by), duration)

    @staticmethod
    def _key_to_seq(key):
        """按键名 → QKeySequence 字符串。"""
        mapping = {
            "space": "Space",
            "r": "R", "s": "S", "f": "F",
            "h": "H", "y": "Y",
        }
        return mapping.get(key, key.capitalize())

    def _setup_shortcuts(self):
        """注册键盘快捷键。"""
        for key, target in self.fsm.KEY_MAP.items():
            seq = self._key_to_seq(key)
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(lambda t=target: self._do_key(t))
            setattr(self, f"_sc_{key}", sc)

    def _do_key(self, target):
        """键盘快捷键触发。"""
        state, speech = self.fsm.on_key(target)
        if state:
            self.set_pose(state)
            self.show_bubble(speech)

    def _greeting(self):
        """开机问候。"""
        msg = greeting_message(self.fsm.hour_fn())
        self.show_bubble(msg, duration=5000)

    def _update_mood_tooltip(self):
        """更新托盘 tooltip 显示心情和互动次数。"""
        tip = f"{self.config.name} | 心情：{self.fsm.mood_label()}({self.fsm.mood}) | 互动：{self.fsm.interaction_count}次"
        if hasattr(self, "tray"):
            self.tray.setToolTip(tip)

    def _setup_tray(self):
        """创建系统托盘菜单。"""
        self.tray = QSystemTrayIcon(self)
        icon_path = os.path.join(SPRITE_DIR, "icon.ico")
        if os.path.exists(icon_path):
            self.tray.setIcon(QIcon(icon_path))
        else:
            self.tray.setIcon(QIcon())
        self.tray.setToolTip(f"{self.config.name} | 桌面宠物")

        self._menu = QMenu()
        m = self._menu

        # 互动组
        m.addAction("点击互动").triggered.connect(self._do_interact)
        m.addAction("挠肚皮（双击）").triggered.connect(self._do_belly_rub)
        m.addAction("摸摸头（长按）").triggered.connect(self._do_pet)
        m.addAction("喂食").triggered.connect(self._do_feed)
        m.addSeparator()

        # 姿势组
        m.addAction("打滚撒娇").triggered.connect(self._do_roll)
        m.addAction("歪歪头").triggered.connect(self._do_head_tilt)
        m.addAction("作揖讨食").triggered.connect(self._do_beg)
        m.addAction("握手").triggered.connect(self._do_shake)
        m.addAction("玩球球").triggered.connect(self._do_play_ball)
        m.addAction("打哈欠").triggered.connect(self._do_yawn)
        m.addSeparator()

        # 功能组
        m.addAction("久坐提醒").triggered.connect(self._do_remind_now)
        m.addAction("去睡觉").triggered.connect(self._do_sleep)
        m.addSeparator()

        # 状态显示（动态）
        self._act_mood = m.addAction(f"心情：{self.fsm.mood_label()}({self.fsm.mood})")
        self._act_mood.setEnabled(False)
        self._act_stats = m.addAction(f"互动次数：{self.fsm.interaction_count}")
        self._act_stats.setEnabled(False)
        m.addSeparator()

        m.addAction("快捷键帮助").triggered.connect(self._show_help)
        m.addAction("退出").triggered.connect(self._do_quit)

        self.tray.setContextMenu(m)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        """托盘图标左键点击 → 互动。"""
        if reason == QSystemTrayIcon.Trigger:
            self._do_interact()

    def _show_help(self):
        """显示快捷键帮助。"""
        help_text = (
            "饼干快捷键：\n"
            "空格 — 开心汪汪\n"
            "R — 打滚撒娇\n"
            "S — 去睡觉\n"
            "F — 作揖讨食\n"
            "H — 握手\n"
            "Y — 打哈欠\n"
            "\n双击 — 挠肚皮\n长按 — 摸摸头"
        )
        self.show_bubble(help_text, duration=6000)

    # ---- 菜单动作 ----
    def _do_interact(self):
        state, speech = self.fsm.on_click()
        self.set_pose(state)
        self.show_bubble(speech)

    def _do_belly_rub(self):
        state, speech = self.fsm.on_double_click()
        self.set_pose(state)
        self.show_bubble(speech)

    def _do_pet(self):
        state, speech = self.fsm.on_pet()
        self.set_pose(state)
        self.show_bubble(speech)

    def _do_feed(self):
        state, speech = self.fsm.on_feed()
        self.set_pose(state)
        self.show_bubble(speech)
        # 1.5 秒后切换到 happy（吃饱）
        QTimer.singleShot(1500, lambda: self._after_feed())

    def _after_feed(self):
        now = time.time()
        self.fsm.state = "happy"
        self.fsm.happy_until = now + STATE_DURATION["happy"]
        self.fsm.state_until = self.fsm.happy_until
        self.set_pose("happy")
        self.show_bubble(f"{self.config.name}：吃饱啦～好满足！")

    def _do_roll(self):
        self.fsm.state = "roll"
        self.fsm.roll_until = time.time() + STATE_DURATION["roll"]
        self.fsm.state_until = self.fsm.roll_until
        self.set_pose("roll")
        self.show_bubble(self.fsm.speech("roll"))

    def _do_head_tilt(self):
        self.fsm.state = "head_tilt"
        self.fsm.state_until = time.time() + STATE_DURATION["head_tilt"]
        self.set_pose("head_tilt")
        self.show_bubble(self.fsm.speech("head_tilt"))

    def _do_beg(self):
        self.fsm.state = "beg"
        self.fsm.state_until = time.time() + STATE_DURATION["beg"]
        self.set_pose("beg")
        self.show_bubble(self.fsm.speech("beg"))

    def _do_shake(self):
        self.fsm.state = "shake"
        self.fsm.state_until = time.time() + STATE_DURATION["shake"]
        self.set_pose("shake")
        self.show_bubble(self.fsm.speech("shake"))

    def _do_play_ball(self):
        self.fsm.state = "play_ball"
        self.fsm.state_until = time.time() + STATE_DURATION["play_ball"]
        self.set_pose("play_ball")
        self.show_bubble(self.fsm.speech("play_ball"))

    def _do_yawn(self):
        self.fsm.state = "yawn"
        self.fsm.state_until = time.time() + STATE_DURATION["yawn"]
        self.set_pose("yawn")
        self.show_bubble(self.fsm.speech("yawn"))

    def _do_remind_now(self):
        msg = self.reminder._pick_message()
        self.set_pose("happy")
        self.show_bubble(msg)

    def _do_sleep(self):
        self.fsm.state = "sleep"
        self.set_pose("sleep")
        self.show_bubble("嘘……饼干睡着啦～")

    def _do_quit(self):
        self.tray.hide()
        QApplication.quit()

    # ---- 初始位置 ----
    def _place_bottom_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - PET_W - 30
        y = screen.bottom() - PET_H - 10
        self.move(x, y)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    pet = PetWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
