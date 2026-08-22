"""UIH · 配置与基本设定测试。"""
import os

from biscuit_pet.core import PetConfig, PET_NAME, POSES, STATE_TO_POSE


def test_UIH_pet_name_is_biscuit():
    cfg = PetConfig()
    assert cfg.name == PET_NAME == "饼干"


def test_UIH_biscuit_has_no_tail():
    """饼干没有尾巴（设定层）。"""
    assert PetConfig().no_tail is True


def test_UIH_realistic_not_cartoon():
    """逼真写实，非卡通化。"""
    assert PetConfig().realistic is True


def test_UIH_all_poses_present():
    """十一种姿势齐备。"""
    expected = {
        "idle", "lie_down", "stare", "roll", "sleep", "happy",
        "head_tilt", "beg", "shake", "play_ball", "yawn",
    }
    assert set(POSES) == expected


def test_UIH_state_to_pose_complete():
    for s in POSES:
        assert STATE_TO_POSE[s] == s


def test_UIH_reminder_default_interval():
    assert PetConfig().reminder_interval_min == 30


def test_UIH_sprite_files_exist():
    here = os.path.dirname(os.path.abspath(__file__))
    sprite_dir = os.path.join(here, "..", "biscuit_pet", "sprites")
    for p in POSES:
        assert os.path.exists(os.path.join(sprite_dir, f"{p}.png")), f"缺少精灵图 {p}.png"
