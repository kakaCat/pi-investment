"""Scheduler repository must expose params as a dict to JobRegistry."""
from types import SimpleNamespace

from adapters.outbound.repositories.scheduler_repository import SchedulerRepository


def _row(params):
    return SimpleNamespace(
        params=params,
        __table__=SimpleNamespace(columns=[SimpleNamespace(key='params')]),
    )


def test_jsonb_string_params_are_decoded_at_repository_boundary():
    repo = SchedulerRepository(session=object())

    data = repo._row_to_dict(_row('{"symbols": ["600519"], "workers": 1}'))

    assert data['params'] == {'symbols': ['600519'], 'workers': 1}


def test_dict_params_are_preserved():
    repo = SchedulerRepository(session=object())
    params = {'account': 'agent_brain'}

    data = repo._row_to_dict(_row(params))

    assert data['params'] == params


def test_invalid_params_string_falls_back_to_empty_mapping():
    repo = SchedulerRepository(session=object())

    data = repo._row_to_dict(_row('{bad json'))

    assert data['params'] == {}
