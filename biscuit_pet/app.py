"""饼干桌面宠物 · Qt 界面层。

基于 PySide6：无边框、半透明、置顶的小狗窗口，支持拖动、点击互动、
右键菜单、系统托盘、久坐提醒气泡、各姿势切换。
"""

import os
import sys
import time

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPixmap, QFont, QCursor, QIcon, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
    QSystemTrayIcon,
    QMenu,
)

from .core import PetConfig, PetFSM, ReminderScheduler, POSES, STATE_TO_POSE

SPRITE_DIR = os.path.join(os.path.dirname(__file__), "sprites")
PET_W, PET_H = 380, 560


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

    def show_message(self, text, top_left):
        self.label.setText(text)
        self.label.adjustSize()
        w, h = self.label.width() + 4, self.label.height() + 4
        self.resize(w, h)
        self.label.setGeometry(0, 0, w, h)
        self.move(top_left)
        self.show()
        self.raise_()
        self._timer.start(4200)


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

        self.fsm = PetFSM(self.config, time_fn=time.time)
        self.reminder = ReminderScheduler(self.config, time_fn=time.time)
        self.bubble = SpeechBubble()

        self._drag_offset = None
        self._cur_pose = None
        self.set_pose("idle")

        # 状态机推进
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.on_tick)
        self.tick_timer.start(900)

        # 久坐提醒检查（每分钟一次）
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self.on_reminder_check)
        self.reminder_timer.start(60000)

        # 随机打滚撒娇（每 2~5 分钟自发一次）
        self.romp_timer = QTimer(self)
        self.romp_timer.setSingleShot(True)
        self.romp_timer.timeout.connect(self.on_romp)
        self.romp_timer.start(120000)

        self._setup_tray()
        self._place_bottom_right()
        self.show()

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
        """自发打滚撒娇。"""
        state, _ = self.fsm.on_click()  # 触发一次互动状态
        if state not in ("roll", "happy"):
            state = "roll"
        self.set_pose(state)
        self.show_bubble(self.fsm.speech(state))
        # 下次随机
        import random

        self.romp_timer.start(int(random.uniform(120, 300)) * 1000)

    # ---- 交互 ----
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            state, speech = self.fsm.on_click()
            self.set_pose(state)
            self.show_bubble(speech)
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, e):
        self._drag_offset = None

    def contextMenuEvent(self, e):
        self._menu.exec(e.globalPos())

    def show_bubble(self, text):
        g = self.geometry()
        bx = g.left() + (g.width() // 2) - 90
        by = g.top() - 60
        self.bubble.show_message(text, QPoint(bx, by))

    # ---- 托盘 ----
    def _setup_tray(self):
        icon_pix = self.sprites.get("idle")
        self.tray = QSystemTrayIcon(QIcon(icon_pix) if icon_pix else QIcon(), self)
        self.tray.setToolTip(f"{self.config.name}·桌面宠物")
        menu = QMenu()
        act_interact = menu.addAction("陪我玩（点击互动）")
        act_roll = menu.addAction("打滚撒娇")
        act_remind = menu.addAction("立刻提醒我动一动")
        act_sleep = menu.addAction("去睡觉")
        menu.addSeparator()
        act_quit = menu.addAction("退出")

        act_interact.triggered.connect(self._do_interact)
        act_roll.triggered.connect(self._do_roll)
        act_remind.triggered.connect(self._do_remind_now)
        act_sleep.triggered.connect(self._do_sleep)
        act_quit.triggered.connect(self._do_quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

        # 托盘图标左键也可互动
        self.tray.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._do_interact()

    # ---- 菜单动作 ----
    def _do_interact(self):
        state, speech = self.fsm.on_click()
        self.set_pose(state)
        self.show_bubble(speech)

    def _do_roll(self):
        self.fsm.state = "roll"
        self.fsm.roll_until = time.time() + 3.0
        self.set_pose("roll")
        self.show_bubble(self.fsm.speech("roll"))

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
