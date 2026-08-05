"""GET /api/evolution/leaderboard FastAPI 路由契约测试（TestClient + mock 仓储层）"""
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _rows():
    return [
        {'account_name': 'agent_virtual', 'window_end': '2026-08-05',
         'up_capture': 1.2, 'down_capture': 0.5, 'fitness': 0.7,
         'up_days': 10, 'down_days': 7, 'status': 'ok'},
        {'account_name': 'v14_simulation', 'window_end': '2026-08-05',
         'up_capture': 0.8, 'down_capture': 1.5, 'fitness': -0.7,
         'up_days': 10, 'down_days': 7, 'status': 'ok'},
    ]


class TestEvolutionLeaderboardRoute:
    def test_success_envelope_and_ranking(self, client):
        with patch(
            'adapters.outbound.repositories.evolution_fitness_repository.EvolutionFitnessORMRepository'
        ) as MockRepo:
            inst = MockRepo.return_value
            inst.get_latest_window_end.return_value = date(2026, 8, 5)
            inst.get_leaderboard.return_value = _rows()
            resp = client.get('/api/evolution/leaderboard', params={'window': 20})
        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True
        data = body['data']
        assert data['windowEnd'] == '2026-08-05'
        ranking = data['ranking']
        assert ranking[0]['accountName'] == 'agent_virtual'
        assert ranking[0]['rank'] == 1
        assert ranking[1]['rank'] == 2

    def test_empty_table_returns_guidance(self, client):
        with patch(
            'adapters.outbound.repositories.evolution_fitness_repository.EvolutionFitnessORMRepository'
        ) as MockRepo:
            inst = MockRepo.return_value
            inst.get_latest_window_end.return_value = None
            resp = client.get('/api/evolution/leaderboard')
        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True
        assert body['data']['ranking'] == []
        assert '尚无适应度数据' in body['data']['message']

    def test_repo_error_returns_500(self, client):
        with patch(
            'adapters.outbound.repositories.evolution_fitness_repository.EvolutionFitnessORMRepository'
        ) as MockRepo:
            MockRepo.return_value.get_latest_window_end.side_effect = RuntimeError('db down')
            resp = client.get('/api/evolution/leaderboard')
        assert resp.status_code == 500
