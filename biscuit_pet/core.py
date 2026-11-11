"""饼干桌面宠物 · 核心逻辑层（无 Qt 依赖，便于单测）。

v2 新增互动：
- 双击 → 挠肚皮（special roll）
- 长按 → 抚摸（head_tilt + 特殊台词）
- 心情系统（互动越频繁心情越高，影响自发行为）
- 时间感知行为（早/中/晚不同状态倾向）
- 喂食互动（beg → happy 序列）
- 键盘快捷键（空格/R/S/F/H）
- 连续点击连击计数 + 特殊台词
- 开机问候
"""

import datetime
import json
import os
import time as _time

PET_NAME = "饼干"

# 全部姿势（11 种）
POSES = [
    "idle", "lie_down", "stare", "roll", "sleep", "happy",
    "head_tilt", "beg", "shake", "play_ball", "yawn",
]

# 状态 -> 姿势文件名
STATE_TO_POSE = {
    "idle": "idle",
    "stare": "stare",
    "roll": "roll",
    "happy": "happy",
    "sleep": "sleep",
    "lie_down": "lie_down",
    "head_tilt": "head_tilt",
    "beg": "beg",
    "shake": "shake",
    "play_ball": "play_ball",
    "yawn": "yawn",
}

# 点击后随机触发的反应状态（v2 扩充：加入 yawn, play_ball）
CLICK_REACTIONS = ["happy", "roll", "stare", "head_tilt", "beg", "shake", "yawn", "play_ball"]

# 各临时状态的持续秒数
STATE_DURATION = {
    "roll": 3.0,
    "happy": 2.5,
    "head_tilt": 2.5,
    "beg": 3.0,
    "shake": 2.5,
    "play_ball": 3.5,
    "yawn": 2.0,
}

# 双击 → 挠肚皮专用台词
BELLY_RUB_SPEECHES = [
    "{name}：嘿嘿～挠肚肚好舒服！",
    "{name}：主人再挠挠～好痒好舒服！",
    "{name}：肚皮朝上～主人快挠！",
]

# 抚摸（长按）专用台词
PET_SPEECHES = [
    "{name}：哼哼～主人摸摸我～",
    "{name}：好舒服～再摸摸～",
    "{name}：主人的手好温暖～",
]

# 喂食台词
FEED_SPEECHES = [
    "{name}：嗷呜～好吃！谢谢主人！",
    "{name}：吧唧吧唧～还有吗？",
    "{name}：吃饱啦～开心！",
]

# 连击里程碑台词
COMBO_SPEECHES = {
    5: "哇！主人好热情～",
    10: "十连击！饼干好开心！",
    20: "二十连击！主人最爱饼干！",
}

# 开机问候（按时间段）
def greeting_message(hour):
    if 6 <= hour < 11:
        return f"{PET_NAME}：早安主人！新的一天～陪我玩吧！"
    elif 11 <= hour < 14:
        return f"{PET_NAME}：中午啦～主人吃饭了吗？"
    elif 14 <= hour < 18:
        return f"{PET_NAME}：下午好～陪我玩球球好不好？"
    elif 18 <= hour < 22:
        return f"{PET_NAME}：晚上好～今天辛苦啦！"
    else:
        return f"{PET_NAME}：夜深了～主人早点休息哦……"


class PetConfig:
    """饼干的基本设定。"""

    def __init__(self):
        self.name = PET_NAME
        self.no_tail = True
        self.realistic = True
        self.reminder_interval_min = 45
        self.activity_reminder_after_min = 3  # 久坐提醒后 3 分钟提示活动结束
        self.idle_to_sleep_sec = 120
        self.reminder_enabled = True
        self.mood_decay_sec = 60       # 心情每 60 秒衰减 1 点
        self.mood_click_gain = 5       # 每次互动 +5 心情
        self.mood_max = 100


class PetFSM:
    """状态机 + 心情系统 + 互动入口。

    互动入口：on_click / on_double_click / on_pet / on_feed / on_key
    每帧调用 tick 推进状态。
    """

    # 键盘快捷键 → 状态
    KEY_MAP = {
        "space": "happy",
        "r": "roll",
        "s": "sleep",
        "f": "beg",       # feed
        "h": "shake",     # handshake
        "y": "yawn",
    }

    def __init__(self, config=None, time_fn=None, rng=None, hour_fn=None):
        self.config = config or PetConfig()
        self.time_fn = time_fn or (lambda: 0.0)
        self.rng = rng or __import__("random").Random()
        self.hour_fn = hour_fn or (lambda: datetime.datetime.now().hour)
        self.state = "idle"
        self.last_interaction = self.time_fn()
        self.roll_until = 0.0
        self.happy_until = 0.0
        self.state_until = 0.0

        # 心情系统
        self.mood = 50
        self._last_mood_update = self.time_fn()
        self.interaction_count = 0
        self.combo_count = 0          # 连续点击计数
        self._last_click_time = 0.0

    # ---- 心情 ----
    def _update_mood(self, now):
        elapsed = now - self._last_mood_update
        decay = int(elapsed / self.config.mood_decay_sec)
        if decay > 0:
            self.mood = max(0, self.mood - decay)
            self._last_mood_update = now
        return self.mood

    def _gain_mood(self, amount):
        self.mood = min(self.config.mood_max, self.mood + amount)

    def mood_label(self):
        if self.mood >= 75:
            return "开心"
        elif self.mood >= 40:
            return "平静"
        elif self.mood >= 15:
            return "无聊"
        else:
            return "想睡觉"

    # ---- 互动入口 ----
    def on_click(self, now=None):
        """单击：随机反应 + 连击计数。"""
        if now is None:
            now = self.time_fn()
        self.last_interaction = now
        self._update_mood(now)
        self._gain_mood(self.config.mood_click_gain)
        self.interaction_count += 1

        # 连击计数（2 秒内连续点击）
        if now - self._last_click_time < 2.0:
            self.combo_count += 1
        else:
            self.combo_count = 1
        self._last_click_time = now

        # 连击里程碑
        combo_speech = ""
        if self.combo_count in COMBO_SPEECHES:
            combo_speech = COMBO_SPEECHES[self.combo_count].format(name=self.config.name)

        self.state = self.rng.choice(CLICK_REACTIONS)
        dur = STATE_DURATION.get(self.state, 3.0)
        self.state_until = now + dur
        if self.state == "roll":
            self.roll_until = self.state_until
        elif self.state == "happy":
            self.happy_until = self.state_until

        speech = self.speech(self.state)
        if combo_speech:
            speech = combo_speech
        return self.state, speech

    def on_double_click(self, now=None):
        """双击 → 挤肚皮（roll + 特殊台词）。"""
        if now is None:
            now = self.time_fn()
        self.last_interaction = now
        self._update_mood(now)
        self._gain_mood(self.config.mood_click_gain + 3)
        self.interaction_count += 1
        self.state = "roll"
        self.roll_until = now + STATE_DURATION["roll"]
        self.state_until = self.roll_until
        speech = self.rng.choice(BELLY_RUB_SPEECHES).format(name=self.config.name)
        return self.state, speech

    def on_pet(self, now=None):
        """长按抚摸 → head_tilt + 特殊台词。"""
        if now is None:
            now = self.time_fn()
        self.last_interaction = now
        self._update_mood(now)
        self._gain_mood(self.config.mood_click_gain + 2)
        self.interaction_count += 1
        self.state = "head_tilt"
        self.state_until = now + STATE_DURATION["head_tilt"]
        speech = self.rng.choice(PET_SPEECHES).format(name=self.config.name)
        return self.state, speech

    def on_feed(self, now=None):
        """喂食 → beg（讨食）→ happy（吃饱）。"""
        if now is None:
            now = self.time_fn()
        self.last_interaction = now
        self._update_mood(now)
        self._gain_mood(self.config.mood_click_gain + 5)
        self.interaction_count += 1
        self.state = "beg"
        self.state_until = now + STATE_DURATION["beg"]
        speech = self.rng.choice(FEED_SPEECHES).format(name=self.config.name)
        return self.state, speech

    def on_key(self, key, now=None):
        """键盘快捷键。"""
        key = key.lower()
        target = self.KEY_MAP.get(key)
        if target is None:
            return self.state, ""
        if now is None:
            now = self.time_fn()
        self.last_interaction = now
        self._update_mood(now)
        self._gain_mood(self.config.mood_click_gain)
        self.interaction_count += 1
        self.state = target
        if target == "roll":
            self.roll_until = now + STATE_DURATION["roll"]
            self.state_until = self.roll_until
        elif target == "happy":
            self.happy_until = now + STATE_DURATION["happy"]
            self.state_until = self.happy_until
        elif target == "sleep":
            self.state_until = 0  # sleep 不自动过期
        else:
            self.state_until = now + STATE_DURATION.get(target, 3.0)
        return self.state, self.speech(target)

    # ---- 台词 ----
    def speech(self, state):
        return {
            "happy": f"{self.config.name}：汪！主人你来啦～",
            "roll": f"{self.config.name}：主人陪我玩嘛～（打滚撒娇）",
            "stare": f"{self.config.name}：……（大眼睛专注地望着你）",
            "idle": f"{self.config.name}：哼哼～",
            "lie_down": f"{self.config.name}：趴着歇会儿～",
            "sleep": f"{self.config.name}：Zzz……",
            "head_tilt": f"{self.config.name}：歪头～主人在说什么呀？",
            "beg": f"{self.config.name}：作揖作揖！有零食吗～",
            "shake": f"{self.config.name}：握手握手～嘿嘿！",
            "play_ball": f"{self.config.name}：球球！主人陪我玩球球好不好？",
            "yawn": f"{self.config.name}：哈欠～好困哦……",
        }.get(state, "")

    # ---- 时间感知 ----
    def time_aware_state(self):
        """根据当前时间段返回建议状态（用于自发行为）。"""
        hour = self.hour_fn()
        if 6 <= hour < 11:
            return self.rng.choice(["beg", "happy", "play_ball"])
        elif 11 <= hour < 14:
            return self.rng.choice(["yawn", "lie_down", "beg"])
        elif 14 <= hour < 18:
            return self.rng.choice(["play_ball", "shake", "happy"])
        elif 18 <= hour < 22:
            return self.rng.choice(["head_tilt", "shake", "happy"])
        else:
            return "sleep"

    # ---- 每帧推进 ----
    def tick(self, now=None):
        if now is None:
            now = self.time_fn()
        prev = self.state
        self._update_mood(now)

        # 互动状态到期回到 idle
        if self.state == "roll" and now >= self.roll_until:
            self.state = "idle"
        if self.state == "happy" and now >= self.happy_until:
            self.state = "idle"
        if self.state in ("head_tilt", "beg", "shake", "play_ball", "yawn") and now >= self.state_until:
            self.state = "idle"
        # 睡觉中被打断
        if self.state == "sleep" and (now - self.last_interaction) < 2.0:
            self.state = "idle"
        # idle/stare 闲置逻辑
        if self.state in ("idle", "stare"):
            # 心情低时更容易睡觉
            sleep_threshold = self.config.idle_to_sleep_sec
            if self.mood < 20:
                sleep_threshold = max(30, sleep_threshold // 3)
            if (now - self.last_interaction) > sleep_threshold:
                self.state = "sleep"
            elif self.rng.random() < 0.02:
                self.state = "stare" if self.state == "idle" else "idle"
        return self.state, (self.state != prev)

    def pose(self):
        return STATE_TO_POSE.get(self.state, "idle")


class ReminderScheduler:
    """久坐提醒（两段式）：每 45 分钟提醒起身，3 分钟后再提示活动结束。

    节奏：久坐 45 分钟 → 「该起来动一动」→ 3 分钟活动 → 「活动结束，继续加油」→ 循环。
    """

    REMINDER_MESSAGES = [
        "{name}提醒：主人已经坐了 45 分钟啦，起来活动 3 分钟吧！伸个懒腰～",
        "{name}提醒：主人，坐了 45 分钟了，该活动活动啦，陪我走走好不好？",
        "{name}提醒：久坐伤身哦，主人快起来动一动，3 分钟就好！",
        "{name}提醒：主人，站起来扭扭腰动一动，饼干给你加油！",
    ]

    ACTIVITY_MESSAGES = [
        "{name}提醒：3 分钟活动时间到！主人休息好啦，继续加油～",
        "{name}提醒：动完啦？主人今天也辛苦了，饼干给你充电！",
    ]

    def __init__(self, config, time_fn=None, rng=None):
        self.config = config
        self.time_fn = time_fn or (lambda: 0.0)
        self.rng = rng or __import__("random").Random()
        self.next_due = self.time_fn() + config.reminder_interval_min * 60
        self.activity_due = None  # 活动结束提醒时刻（触发久坐提醒后设置）

    def check(self, now=None):
        if not self.config.reminder_enabled:
            return False, None
        if now is None:
            now = self.time_fn()
        # 活动结束提醒优先（处于活动窗口中时不看久坐计时）
        if self.activity_due is not None:
            if now >= self.activity_due:
                self.activity_due = None
                self.next_due = now + self.config.reminder_interval_min * 60
                return True, self._pick_message(self.ACTIVITY_MESSAGES)
            return False, None
        if now >= self.next_due:
            self.activity_due = now + self.config.activity_reminder_after_min * 60
            return True, self._pick_message(self.REMINDER_MESSAGES)
        return False, None

    def _pick_message(self, msgs=None):
        tpl = self.rng.choice(msgs or self.REMINDER_MESSAGES)
        return tpl.format(name=self.config.name)

    def snooze(self, minutes, now=None):
        if now is None:
            now = self.time_fn()
        self.next_due = now + minutes * 60
        self.activity_due = None  # 推迟时取消未触发的活动提醒


class TimedReminder:
    """定时提醒：用户自定义 HH:MM + 提醒内容，每天到点触发一次。

    - 同一时间的旧提醒会被新提醒覆盖
    - 每条提醒每天最多触发一次（按日期去重）
    - 触发后有 CATCHUP_MIN 分钟追补窗口（应用刚启动时不会漏掉刚过的点）
    - 提醒列表持久化到 JSON 文件，重启后保留
    """

    CATCHUP_MIN = 15  # 追补窗口（分钟）

    def __init__(self, config, time_fn=None, store_path=None):
        self.config = config
        self.time_fn = time_fn or (lambda: _time.time())
        self.store_path = store_path  # None 时不持久化
        self.reminders = []  # [{"time": "HH:MM", "text": str, "last_fired": "YYYY-MM-DD"}]
        self.load()

    # ---- 增删查 ----
    @staticmethod
    def _norm_hhmm(hhmm):
        """归一化时间字符串，合法返回 'HH:MM'，否则返回 None。"""
        if not isinstance(hhmm, str):
            return None
        s = hhmm.strip().replace("：", ":")
        for sep in (":",):
            parts = s.split(sep)
            if len(parts) != 2:
                continue
            try:
                h, m = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            if 0 <= h <= 23 and 0 <= m <= 59:
                return f"{h:02d}:{m:02d}"
        return None

    def add(self, hhmm, text):
        """添加（或覆盖同一时间的）提醒。成功返回 True。"""
        t = self._norm_hhmm(hhmm)
        text = (text or "").strip()
        if t is None or not text:
            return False
        self.remove(t)
        self.reminders.append({"time": t, "text": text, "last_fired": ""})
        self.reminders.sort(key=lambda r: r["time"])
        self.save()
        return True

    def remove(self, hhmm):
        """删除指定时间的提醒，返回是否删除了至少一条。"""
        t = self._norm_hhmm(hhmm) or hhmm
        before = len(self.reminders)
        self.reminders = [r for r in self.reminders if r["time"] != t]
        changed = len(self.reminders) < before
        if changed:
            self.save()
        return changed

    def clear(self):
        self.reminders = []
        self.save()

    def items(self):
        return [dict(r) for r in self.reminders]

    # ---- 触发检查 ----
    def check(self, now=None):
        """返回本轮触发的提醒文本列表（已标记当天已触发）。"""
        if now is None:
            now = self._now()
        elif isinstance(now, (int, float)):
            now = datetime.datetime.fromtimestamp(now)
        today = now.strftime("%Y-%m-%d")
        fired = []
        for r in self.reminders:
            if r.get("last_fired") == today:
                continue
            try:
                rt = datetime.datetime.strptime(r["time"], "%H:%M").time()
            except ValueError:
                continue
            due_dt = now.replace(hour=rt.hour, minute=rt.minute, second=0, microsecond=0)
            delta_min = (now - due_dt).total_seconds() / 60.0
            if 0 <= delta_min <= self.CATCHUP_MIN:
                r["last_fired"] = today
                fired.append(f"⏰ {self.config.name}的定时提醒：{r['text']}")
        if fired:
            self.save()
        return fired

    # ---- 持久化 ----
    def save(self):
        if not self.store_path:
            return
        try:
            d = os.path.dirname(self.store_path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(self.reminders, f, ensure_ascii=False, indent=1)
        except OSError:
            pass  # 持久化失败不影响运行

    def load(self):
        if not self.store_path or not os.path.exists(self.store_path):
            return
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.reminders = [
                    {"time": r.get("time", ""), "text": r.get("text", ""),
                     "last_fired": r.get("last_fired", "")}
                    for r in data if isinstance(r, dict)
                ]
        except (OSError, ValueError):
            pass  # 文件损坏时忽略，按空列表处理
