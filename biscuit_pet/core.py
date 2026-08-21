"""饼干桌面宠物 · 核心逻辑层（无 Qt 依赖，便于单测）。"""

PET_NAME = "饼干"

# 全部姿势
POSES = ["idle", "lie_down", "stare", "roll", "sleep", "happy"]

# 状态 -> 姿势文件名
STATE_TO_POSE = {
    "idle": "idle",
    "stare": "stare",
    "roll": "roll",
    "happy": "happy",
    "sleep": "sleep",
    "lie_down": "lie_down",
}


class PetConfig:
    """饼干的基本设定。"""

    def __init__(self):
        self.name = PET_NAME                 # 名字：饼干
        self.no_tail = True                  # 饼干没有尾巴
        self.realistic = True                # 逼真写实，非卡通化
        self.reminder_interval_min = 30      # 提醒主人动一动的间隔（分钟）
        self.idle_to_sleep_sec = 120         # 闲置多久后自动睡觉（秒）
        self.reminder_enabled = True         # 是否开启久坐提醒


class PetFSM:
    """状态机：idle / stare / roll / happy / sleep。

    互动入口 on_click；每帧调用 tick 推进状态。
    所有时间参数可注入，便于测试。
    """

    def __init__(self, config=None, time_fn=None, rng=None):
        self.config = config or PetConfig()
        self.time_fn = time_fn or (lambda: 0.0)
        self.rng = rng or __import__("random").Random()
        self.state = "idle"
        self.last_interaction = self.time_fn()
        self.roll_until = 0.0
        self.happy_until = 0.0

    # ---- 互动 ----
    def on_click(self, now=None):
        """点击饼干：随机返回一个反应状态 + 台词。"""
        if now is None:
            now = self.time_fn()
        self.last_interaction = now
        self.state = self.rng.choice(["happy", "roll", "stare"])
        if self.state == "roll":
            self.roll_until = now + 3.0
        elif self.state == "happy":
            self.happy_until = now + 2.5
        return self.state, self.speech(self.state)

    def speech(self, state):
        return {
            "happy": f"{self.config.name}：汪！主人你来啦～",
            "roll": f"{self.config.name}：主人陪我玩嘛～（打滚撒娇）",
            "stare": f"{self.config.name}：……（大眼睛专注地望着你）",
            "idle": f"{self.config.name}：哼哼～",
            "lie_down": f"{self.config.name}：趴着歇会儿～",
            "sleep": f"{self.config.name}：Zzz……",
        }.get(state, "")

    # ---- 每帧推进 ----
    def tick(self, now=None):
        if now is None:
            now = self.time_fn()
        prev = self.state
        # 互动状态到期回到 idle
        if self.state == "roll" and now >= self.roll_until:
            self.state = "idle"
        if self.state == "happy" and now >= self.happy_until:
            self.state = "idle"
        # 睡觉中被打断（最近 2 秒有过互动）-> 醒来
        if self.state == "sleep" and (now - self.last_interaction) < 2.0:
            self.state = "idle"
        # idle/stare 闲置逻辑
        if self.state in ("idle", "stare"):
            if (now - self.last_interaction) > self.config.idle_to_sleep_sec:
                self.state = "sleep"
            elif self.rng.random() < 0.02:
                # 偶尔切换 idle<->stare，模拟大眼睛注视
                self.state = "stare" if self.state == "idle" else "idle"
        return self.state, (self.state != prev)

    def pose(self):
        return STATE_TO_POSE.get(self.state, "idle")


class ReminderScheduler:
    """久坐提醒：到点提醒主人起来动一动。"""

    REMINDER_MESSAGES = [
        "{name}提醒：主人坐太久啦，起来动一动吧！伸个懒腰～",
        "{name}提醒：主人，该活动活动啦，陪我走走好不好？",
        "{name}提醒：久坐伤身哦，主人快起来动一动！",
        "{name}提醒：主人，站起来扭扭腰，饼干给你加油！",
    ]

    def __init__(self, config, time_fn=None, rng=None):
        self.config = config
        self.time_fn = time_fn or (lambda: 0.0)
        self.rng = rng or __import__("random").Random()
        self.next_due = self.time_fn() + config.reminder_interval_min * 60

    def check(self, now=None):
        if not self.config.reminder_enabled:
            return False, None
        if now is None:
            now = self.time_fn()
        if now >= self.next_due:
            self.next_due = now + self.config.reminder_interval_min * 60
            return True, self._pick_message()
        return False, None

    def _pick_message(self):
        tpl = self.rng.choice(self.REMINDER_MESSAGES)
        return tpl.format(name=self.config.name)

    def snooze(self, minutes, now=None):
        """推迟下一次提醒。"""
        if now is None:
            now = self.time_fn()
        self.next_due = now + minutes * 60
