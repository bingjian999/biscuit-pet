"""UIH · 状态机（互动/打滚/睡觉/大眼睛注视）测试。"""
import random

from biscuit_pet.core import PetConfig, PetFSM, POSES, CLICK_REACTIONS, STATE_DURATION, greeting_message


def _fsm(t0=0.0):
    t = {"v": t0}
    return PetFSM(PetConfig(), time_fn=lambda: t["v"], rng=random.Random(7)), t


def test_UIH_click_returns_reaction_and_speech():
    fsm, t = _fsm()
    state, speech = fsm.on_click(now=1.0)
    assert state in CLICK_REACTIONS
    assert "饼干" in speech


def test_UIH_roll_expires_back_to_idle():
    class RngNoToggle:
        def choice(self, seq):
            return seq[0]

        def random(self):
            return 1.0  # 永不触发 idle<->stare 随机切换

    fsm, t = _fsm()
    fsm.rng = RngNoToggle()
    fsm.state = "roll"
    fsm.roll_until = 1.0
    fsm.last_interaction = 0.0
    # 打滚状态在到期后回到 idle
    state, _ = fsm.tick(now=1.5)
    assert state == "idle"


def test_UIH_happy_expires_back_to_idle():
    fsm, t = _fsm()
    fsm.state = "happy"
    fsm.happy_until = 5.0
    state, _ = fsm.tick(now=6.0)
    assert state == "idle"


def test_UIH_long_idle_goes_sleep():
    fsm, t = _fsm()
    fsm.on_click(now=0.0)
    # 超过 idle_to_sleep_sec(120) 后睡觉
    state, _ = fsm.tick(now=1000.0)
    assert state == "sleep"


def test_UIH_sleep_interrupted_by_recent_interaction():
    fsm, t = _fsm()
    fsm.state = "sleep"
    fsm.last_interaction = 8.0  # 最近互动过
    state, _ = fsm.tick(now=9.0)
    assert state == "idle"


def test_UIH_pose_matches_state():
    fsm, t = _fsm()
    for s in POSES:
        fsm.state = s
        assert fsm.pose() == s


def test_UIH_click_updates_last_interaction():
    fsm, t = _fsm()
    fsm.on_click(now=10.0)
    assert fsm.last_interaction == 10.0


def test_UIH_click_reactions_include_new_poses():
    """点击反应池包含新增姿势。"""
    for pose in ("head_tilt", "beg", "shake"):
        assert pose in CLICK_REACTIONS


def test_UIH_new_temp_states_expire_to_idle():
    """新增临时状态（head_tilt/beg/shake/play_ball/yawn）到期后回到 idle。"""
    fsm, t = _fsm()
    for pose in ("head_tilt", "beg", "shake", "play_ball", "yawn"):
        fsm.state = pose
        fsm.state_until = 5.0
        state, _ = fsm.tick(now=6.0)
        assert state == "idle", f"{pose} should expire to idle"


def test_UIH_new_pose_speech_has_name():
    """新增姿势台词都含饼干名字。"""
    fsm, t = _fsm()
    for pose in ("head_tilt", "beg", "shake", "play_ball", "yawn"):
        text = fsm.speech(pose)
        assert "饼干" in text, f"{pose} speech should contain name"


def test_UIH_state_duration_defined_for_all_temp():
    """所有临时状态都有持续时长。"""
    for pose in ("roll", "happy", "head_tilt", "beg", "shake", "play_ball", "yawn"):
        assert pose in STATE_DURATION


# ---- v2 新互动测试 ----

def test_UIH_double_click_triggers_belly_rub():
    """双击 → roll + 挤肚皮台词。"""
    fsm, t = _fsm()
    state, speech = fsm.on_double_click(now=1.0)
    assert state == "roll"
    assert "饼干" in speech
    assert fsm.roll_until > 1.0


def test_UIH_pet_triggers_head_tilt():
    """长按抚摸 → head_tilt + 抚摸台词。"""
    fsm, t = _fsm()
    state, speech = fsm.on_pet(now=2.0)
    assert state == "head_tilt"
    assert "饼干" in speech


def test_UIH_feed_triggers_beg():
    """喂食 → beg（讨食）。"""
    fsm, t = _fsm()
    state, speech = fsm.on_feed(now=3.0)
    assert state == "beg"
    assert "饼干" in speech


def test_UIH_key_space_to_happy():
    """空格键 → happy。"""
    fsm, t = _fsm()
    state, speech = fsm.on_key("space", now=1.0)
    assert state == "happy"
    assert "饼干" in speech


def test_UIH_key_r_to_roll():
    """R 键 → roll。"""
    fsm, t = _fsm()
    state, _ = fsm.on_key("r", now=1.0)
    assert state == "roll"


def test_UIH_key_s_to_sleep():
    """S 键 → sleep。"""
    fsm, t = _fsm()
    state, _ = fsm.on_key("s", now=1.0)
    assert state == "sleep"


def test_UIH_key_y_to_yawn():
    """Y 键 → yawn。"""
    fsm, t = _fsm()
    state, _ = fsm.on_key("y", now=1.0)
    assert state == "yawn"


def test_UIH_key_unknown_no_effect():
    """未知按键 → 返回当前状态，不触发互动。"""
    fsm, t = _fsm()
    orig_state = fsm.state
    state, speech = fsm.on_key("z", now=1.0)
    assert state == orig_state
    assert speech == ""


def test_UIH_mood_starts_at_50():
    """心情初始值 50。"""
    fsm, t = _fsm()
    assert fsm.mood == 50


def test_UIH_mood_gains_on_click():
    """点击后心情增加。"""
    fsm, t = _fsm()
    fsm.on_click(now=1.0)
    assert fsm.mood > 50


def test_UIH_mood_decays_over_time():
    """心情随时间衰减。"""
    fsm, t = _fsm()
    fsm.mood = 80
    fsm._last_mood_update = 0.0
    fsm._update_mood(now=200.0)  # 200 秒 / 60 秒衰减 = 3 点
    assert fsm.mood == 77


def test_UIH_mood_label_thresholds():
    """心情标签阈值正确。"""
    fsm, t = _fsm()
    fsm.mood = 80
    assert fsm.mood_label() == "开心"
    fsm.mood = 50
    assert fsm.mood_label() == "平静"
    fsm.mood = 20
    assert fsm.mood_label() == "无聊"
    fsm.mood = 10
    assert fsm.mood_label() == "想睡觉"


def test_UIH_combo_count_resets():
    """连击计数在 2 秒后重置。"""
    fsm, t = _fsm()
    fsm.on_click(now=1.0)
    assert fsm.combo_count == 1
    fsm.on_click(now=1.5)
    assert fsm.combo_count == 2
    # 超过 2 秒后重置
    fsm.on_click(now=5.0)
    assert fsm.combo_count == 1


def test_UIH_interaction_count_increments():
    """互动次数计数。"""
    fsm, t = _fsm()
    assert fsm.interaction_count == 0
    fsm.on_click(now=1.0)
    fsm.on_pet(now=2.0)
    fsm.on_feed(now=3.0)
    assert fsm.interaction_count == 3


def test_UIH_time_aware_state_returns_valid():
    """时间感知状态返回有效姿势。"""
    fsm, t = _fsm()
    for hour in range(24):
        fsm.hour_fn = lambda h=hour: h
        state = fsm.time_aware_state()
        assert state in POSES


def test_UIH_greeting_message_contains_name():
    """问候消息包含饼干名字。"""
    for hour in range(24):
        msg = greeting_message(hour)
        assert "饼干" in msg
