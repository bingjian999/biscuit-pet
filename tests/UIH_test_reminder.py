"""UIH · 久坐提醒调度测试。"""
import random

from biscuit_pet.core import PetConfig, ReminderScheduler


def _sched(t0=0.0, interval=30):
    t = {"v": t0}
    cfg = PetConfig()
    cfg.reminder_interval_min = interval
    return ReminderScheduler(cfg, time_fn=lambda: t["v"], rng=random.Random(1)), t


def test_UIH_reminder_not_due_before_interval():
    sch, t = _sched(interval=30)
    t["v"] = 60 * 29
    due, msg = sch.check()
    assert due is False and msg is None


def test_UIH_reminder_due_after_interval():
    sch, t = _sched(interval=30)
    t["v"] = 60 * 30 + 1
    due, msg = sch.check()
    assert due is True
    assert "饼干" in msg
    assert "动一动" in msg or "活动" in msg or "动" in msg


def test_UIH_reminder_reschedules_after_fire():
    sch, t = _sched(interval=30)
    t["v"] = 60 * 30
    due, _ = sch.check()
    assert due is True
    # 刚提醒过，短时间内不再提醒
    t["v"] = 60 * 30 + 5
    due2, _ = sch.check()
    assert due2 is False
    # 又过了一个周期才再次提醒
    t["v"] = 60 * 60 + 1
    due3, _ = sch.check()
    assert due3 is True


def test_UIH_reminder_can_be_disabled():
    sch, t = _sched()
    sch.config.reminder_enabled = False
    t["v"] = 60 * 60 * 10
    due, msg = sch.check()
    assert due is False and msg is None


def test_UIH_reminder_snooze():
    sch, t = _sched(interval=30)
    t["v"] = 60 * 30
    sch.check()  # 触发一次
    sch.snooze(5, now=60 * 30)  # 推迟 5 分钟
    t["v"] = 60 * 35 - 1
    due, _ = sch.check()
    assert due is False
    t["v"] = 60 * 35 + 1
    due, _ = sch.check()
    assert due is True


# ---- 两段式节奏：45 分钟久坐 + 3 分钟活动 ----

def test_UIH_reminder_sedentary_then_activity():
    """久坐提醒后 3 分钟触发活动结束提醒。"""
    sch, t = _sched(interval=45)
    t["v"] = 60 * 45
    due, msg = sch.check()
    assert due is True
    assert "活动" in msg or "动" in msg          # 久坐提醒
    # 活动窗口内（3 分钟内）不再打扰
    t["v"] = 60 * 45 + 60 * 3 - 1
    due, msg = sch.check()
    assert due is False and msg is None
    # 3 分钟到 → 活动结束提醒
    t["v"] = 60 * 45 + 60 * 3
    due, msg = sch.check()
    assert due is True and ("活动时间到" in msg or "动完" in msg)
    # 活动提醒只触发一次
    t["v"] = 60 * 45 + 60 * 3 + 10
    due, _ = sch.check()
    assert due is False


def test_UIH_reminder_cycle_repeats_after_activity():
    """活动结束后进入下一个 45 分钟周期。"""
    sch, t = _sched(interval=45)
    t["v"] = 60 * 45
    sch.check()                                   # 久坐提醒
    t["v"] = 60 * 48
    sch.check()                                   # 活动结束提醒
    t["v"] = 60 * 48 + 60 * 45 - 1
    due, _ = sch.check()
    assert due is False
    t["v"] = 60 * 48 + 60 * 45 + 1
    due, _ = sch.check()
    assert due is True


def test_UIH_reminder_snooze_cancels_pending_activity():
    """推迟久坐提醒时，未触发的活动提醒一并取消。"""
    sch, t = _sched(interval=45)
    t["v"] = 60 * 45
    sch.check()                                   # 久坐提醒（活动提醒待触发）
    sch.snooze(10, now=60 * 45)
    t["v"] = 60 * 48 + 5                          # 原活动提醒时刻已过
    due, _ = sch.check()
    assert due is False                           # 不应触发活动提醒
