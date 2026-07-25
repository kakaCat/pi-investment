"""
POST /api/scheduler/start 的双调度器防护测试。

背景（2026-07-23 code review 发现#5）：
该接口会在 web 进程内启动第二个 BackgroundScheduler，绑定与
scheduler_daemon 相同的 apscheduler_jobs 表。APScheduler 无跨进程锁，
两个调度器会重复执行所有任务。启动前必须检查共享 jobstore 是否已有
daemon 注册的任务，有则拒绝（可用 ?force=true 显式覆盖）。
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from adapters.inbound.api.routes.scheduler_enterprise import scheduler_enterprise_bp

ROUTE_MOD = 'adapters.inbound.api.routes.scheduler_enterprise'


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(scheduler_enterprise_bp)
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestStartSchedulerGuard:
    def test_refuses_when_jobstore_has_daemon_jobs(self, client):
        """共享 jobstore 已有任务（daemon 在跑）时拒绝启动第二调度器"""
        mock_scheduler = MagicMock()
        with patch(f'{ROUTE_MOD}.get_scheduler', return_value=mock_scheduler), \
             patch(f'{ROUTE_MOD}._shared_jobstore_job_count', return_value=7):
            response = client.post('/api/scheduler/start')

        assert response.status_code == 409
        data = json.loads(response.data)
        assert data['success'] is False
        mock_scheduler.start.assert_not_called()

    def test_force_overrides_guard(self, client):
        """显式 force=true 时允许启动（人工确认后的逃生口）"""
        mock_scheduler = MagicMock()
        with patch(f'{ROUTE_MOD}.get_scheduler', return_value=mock_scheduler), \
             patch(f'{ROUTE_MOD}._shared_jobstore_job_count', return_value=7):
            response = client.post('/api/scheduler/start?force=true')

        assert response.status_code == 200
        mock_scheduler.start.assert_called_once()

    def test_starts_when_jobstore_empty(self, client):
        """jobstore 为空（无 daemon）时正常启动"""
        mock_scheduler = MagicMock()
        with patch(f'{ROUTE_MOD}.get_scheduler', return_value=mock_scheduler), \
             patch(f'{ROUTE_MOD}._shared_jobstore_job_count', return_value=0):
            response = client.post('/api/scheduler/start')

        assert response.status_code == 200
        mock_scheduler.start.assert_called_once()
