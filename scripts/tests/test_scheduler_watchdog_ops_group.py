"""调度看门狗告警落点单测（2026-10-14 · 用户裁定分群）。

用户要求：调度看门狗这类**系统消息**不许和「盘前例程」「实盘账户·保护线」这类
**股票消息**混在一个飞书群。

本脚本此前读 FEISHU_WEBHOOK_URL（= 通用群），现改为读运维群专用配置：
    WATCHDOG_FEISHU_WEBHOOK > FEISHU_WEBHOOK_OPS > 内置运维群默认值
且**不再读 FEISHU_WEBHOOK_URL** —— 变量在别处指向通用群，读了就等于混群。

模块在 import 期读环境变量，故每个用例用干净的 env 重新 exec 模块。
"""
import importlib.util
import pathlib

WATCHDOG = pathlib.Path(__file__).resolve().parents[1] / 'scheduler_watchdog.py'
OPS_DEFAULT = "https://open.feishu.cn/open-apis/bot/v2/hook/7aa7ebdd-be9e-47f9-be45-ba9c772499c9"
GENERAL = "https://open.feishu.cn/open-apis/bot/v2/hook/b24be3a5-35fc-4142-90c2-3a3933172829"
OTHER_OPS = "https://open.feishu.cn/open-apis/bot/v2/hook/other-ops-group"


def _load(monkeypatch, **env):
    """在受控环境变量下重新加载看门狗模块。"""
    for key in ("WATCHDOG_FEISHU_WEBHOOK", "FEISHU_WEBHOOK_OPS", "FEISHU_WEBHOOK_URL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    spec = importlib.util.spec_from_file_location('scheduler_watchdog_ops', WATCHDOG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_defaults_to_ops_group(monkeypatch):
    assert _load(monkeypatch).OPS_FEISHU_WEBHOOK == OPS_DEFAULT


def test_general_webhook_env_is_ignored(monkeypatch):
    """关键回归：设了 FEISHU_WEBHOOK_URL（通用群）也不能把它当落点。"""
    mod = _load(monkeypatch, FEISHU_WEBHOOK_URL=GENERAL)
    assert mod.OPS_FEISHU_WEBHOOK == OPS_DEFAULT
    assert mod.OPS_FEISHU_WEBHOOK != GENERAL


def test_feishu_webhook_ops_wins_over_default(monkeypatch):
    assert _load(monkeypatch, FEISHU_WEBHOOK_OPS=OTHER_OPS).OPS_FEISHU_WEBHOOK == OTHER_OPS


def test_watchdog_specific_env_wins_over_all(monkeypatch):
    mod = _load(monkeypatch, WATCHDOG_FEISHU_WEBHOOK=OTHER_OPS,
                FEISHU_WEBHOOK_OPS=OPS_DEFAULT, FEISHU_WEBHOOK_URL=GENERAL)
    assert mod.OPS_FEISHU_WEBHOOK == OTHER_OPS
