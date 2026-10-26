"""DSH 看门狗故障注入测试：未注册、已注册、恢复失败三条路径不得混淆。"""
from __future__ import annotations

import os
import pathlib
import stat
import subprocess

import pytest

WATCHDOG = pathlib.Path(__file__).resolve().parents[1] / "dsh-watchdog.sh"


def _executable(path: pathlib.Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def watchdog_env(tmp_path: pathlib.Path) -> tuple[dict[str, str], pathlib.Path]:
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    plist = tmp_path / "com.pi-investment.dsh.plist"
    plist.write_text("<plist/>")

    # 跳过产物指纹检查（退出码 2 = 旧产物），把本测试限定在进程恢复路径。
    _executable(fakebin / "node", "#!/bin/bash\nexit 2\n")
    _executable(fakebin / "sleep", "#!/bin/bash\nexit 0\n")
    _executable(
        fakebin / "curl",
        """#!/bin/bash
set -u
count_file="$FAKE_STATE/curl-count"
count=0
[ -f "$count_file" ] && count="$(cat "$count_file")"
count=$((count + 1))
printf '%s\n' "$count" > "$count_file"
if [ "${FAKE_CURL_RECOVER:-1}" = "1" ] && [ "$count" -ge 2 ]; then
    printf '401'
else
    printf '000'
fi
""",
    )
    _executable(
        fakebin / "launchctl",
        """#!/bin/bash
set -u
printf '%s\n' "$*" >> "$FAKE_STATE/launchctl-args"
case "${1:-}" in
    print)
        case "$FAKE_LAUNCHD_MODE" in
            missing|bootstrap-fail) exit 1 ;;
        esac
        exit 0
        ;;
    list)
        case "$FAKE_LAUNCHD_MODE" in
            loaded-idle) printf '%s\n' '-\t0\tcom.pi-investment.dsh' ;;
            loaded-running) printf '%s\n' '123\t0\tcom.pi-investment.dsh' ;;
        esac
        ;;
    bootstrap)
        [ "$FAKE_LAUNCHD_MODE" = "bootstrap-fail" ] && { echo 'bootstrap injected failure'; exit 1; }
        ;;
    kickstart)
        [ "$FAKE_LAUNCHD_MODE" = "kickstart-fail" ] && { echo 'kickstart injected failure'; exit 1; }
        ;;
esac
exit 0
""",
    )

    env = os.environ.copy()
    env.update(
        PATH=f"{fakebin}:/usr/bin:/bin",
        FAKE_STATE=str(state),
        FAKE_LAUNCHD_MODE="missing",
        DSH_WATCHDOG_LOG=str(tmp_path / "watchdog.log"),
        DSH_WATCHDOG_PLIST=str(plist),
    )
    return env, state


def _run(env: dict[str, str], mode: str, **updates: str) -> subprocess.CompletedProcess[str]:
    env = env.copy()
    env["FAKE_LAUNCHD_MODE"] = mode
    env.update(updates)
    return subprocess.run(
        ["/bin/bash", str(WATCHDOG)], env=env, text=True, capture_output=True, timeout=10
    )


def test_missing_service_uses_bootstrap_and_recovers(watchdog_env):
    env, state = watchdog_env
    result = _run(env, "missing")

    assert result.returncode == 0, result.stderr
    args = (state / "launchctl-args").read_text()
    assert "bootstrap " in args
    assert "com.pi-investment.dsh.plist" in args
    assert "kickstart" not in args
    log = pathlib.Path(env["DSH_WATCHDOG_LOG"]).read_text()
    assert "launchd 未注册" in log
    assert "复核：已恢复（HTTP 401）" in log


def test_loaded_service_without_pid_uses_kickstart_not_bootstrap(watchdog_env):
    env, state = watchdog_env
    result = _run(env, "loaded-idle")

    assert result.returncode == 0, result.stderr
    args = (state / "launchctl-args").read_text()
    assert "kickstart gui/" in args
    assert "kickstart -k" not in args
    assert "bootstrap" not in args


def test_loaded_running_service_uses_forced_kickstart(watchdog_env):
    env, state = watchdog_env
    result = _run(env, "loaded-running")

    assert result.returncode == 0, result.stderr
    args = (state / "launchctl-args").read_text()
    assert "kickstart -k gui/" in args
    assert "bootstrap" not in args


def test_bootstrap_failure_is_not_reported_as_success(watchdog_env):
    env, state = watchdog_env
    result = _run(env, "bootstrap-fail")

    assert result.returncode != 0
    assert "bootstrap injected failure" in pathlib.Path(env["DSH_WATCHDOG_LOG"]).read_text()
    assert "复核：已恢复" not in pathlib.Path(env["DSH_WATCHDOG_LOG"]).read_text()
    # 动作已失败时不再等待并伪造第二次探活。
    assert not (state / "curl-count").exists() or (state / "curl-count").read_text().strip() == "1"


def test_recheck_failure_returns_nonzero(watchdog_env):
    env, _ = watchdog_env
    result = _run(env, "missing", FAKE_CURL_RECOVER="0")

    assert result.returncode != 0
    assert "复核：仍未恢复" in pathlib.Path(env["DSH_WATCHDOG_LOG"]).read_text()


def test_missing_service_and_plist_fails_before_bootstrap(watchdog_env):
    env, state = watchdog_env
    pathlib.Path(env["DSH_WATCHDOG_PLIST"]).unlink()
    result = _run(env, "missing")

    assert result.returncode != 0
    assert "plist 不存在" in pathlib.Path(env["DSH_WATCHDOG_LOG"]).read_text()
    args = (state / "launchctl-args").read_text()
    assert "bootstrap" not in args
