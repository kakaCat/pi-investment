"""jobs 域 parity 测试（P4）"""
import pytest
from tests.migration.parity import assert_parity

JOBS = "/api/jobs"
JOB_BY_ID = "/api/jobs/nonexistent-id"
JOB_RETRY = "/api/jobs/nonexistent-id/retry"
JOB_CANCEL = "/api/jobs/nonexistent-id/cancel"
JOB_RUN = "/api/jobs/bogus_type/run"


def test_list_jobs(fastapi_client):
    assert_parity(fastapi_client, "GET", JOBS, params={"page": 1, "pageSize": 5})


def test_get_job_not_found(fastapi_client):
    assert_parity(fastapi_client, "GET", JOB_BY_ID)


def test_retry_job_not_found(fastapi_client):
    assert_parity(fastapi_client, "POST", JOB_RETRY, json_body={})


def test_cancel_job_not_found(fastapi_client):
    assert_parity(fastapi_client, "POST", JOB_CANCEL, json_body={})


def test_run_job_invalid_type(fastapi_client):
    assert_parity(fastapi_client, "POST", JOB_RUN, json_body={})
