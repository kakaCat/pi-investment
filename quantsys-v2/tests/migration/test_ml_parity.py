"""ml 域 parity 测试（P8）

features/model-info 是确定性读 → 全量 parity。
train/predict 是重量级 ML 操作（训练/预测输出易变、写 DB），只做错误路径 parity。
"""
import pytest
from tests.migration.parity import assert_parity

FEATURES = "/api/ml/features"
MODEL_INFO = "/api/ml/model/info"
TRAIN = "/api/ml/train"
PREDICT = "/api/ml/predict"


def test_features(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", FEATURES)


def test_model_info(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", MODEL_INFO)


def test_train_invalid_model_type(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", TRAIN,
                  json_body={"model_type": "bogus", "symbols": ["600519"]})


def test_predict_missing_symbols(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", PREDICT, json_body={"symbols": []})
