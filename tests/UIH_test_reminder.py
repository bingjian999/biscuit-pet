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
