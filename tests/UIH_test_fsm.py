"""UIH · 状态机（互动/打滚/睡觉/大眼睛注视）测试。"""
import random

from biscuit_pet.core import PetConfig, PetFSM


def _fsm(t0=0.0):
    t = {"v": t0}
    return PetFSM(PetConfig(), time_fn=lambda: t["v"], rng=random.Random(7)), t


def test_UIH_click_returns_reaction_and_speech():
    fsm, t = _fsm()
    state, speech = fsm.on_click(now=1.0)
    assert state in ("happy", "roll", "stare")
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
    for s in ("idle", "stare", "roll", "happy", "sleep", "lie_down"):
        fsm.state = s
        assert fsm.pose() == s


def test_UIH_click_updates_last_interaction():
    fsm, t = _fsm()
    fsm.on_click(now=10.0)
    assert fsm.last_interaction == 10.0
