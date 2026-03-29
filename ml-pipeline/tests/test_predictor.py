import os
import pickle
import tempfile
import unittest

import numpy as np
import pandas as pd

from inference.predictor import SignalPredictor


class DummyModel:
    def predict_proba(self, X):
        return np.array([[0.2, 0.8] for _ in range(len(X))])


class TestSignalPredictor(unittest.TestCase):
    def test_predict_returns_positive_class_probability(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = os.path.join(temp_dir, 'signal_model.pkl')
            with open(model_path, 'wb') as model_file:
                pickle.dump(DummyModel(), model_file)

            predictor = SignalPredictor(model_path=model_path)
            X = pd.DataFrame({'feature_a': [1.0], 'feature_b': [2.0]})

            proba = predictor.predict(X)

        self.assertEqual(proba.tolist(), [0.8])
