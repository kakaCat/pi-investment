"""
基础模型训练脚本
支持：LightGBM、XGBoost、CatBoost
交叉验证 + 模型融合
"""

import os
import pandas as pd
import numpy as np
import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoostClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
import warnings
warnings.filterwarnings('ignore')

class TianchiTrainer:
    """天池模型训练器"""

    def __init__(self, data_dir='./processed_data', output_dir='./models'):
        self.data_dir = data_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def load_fold_data(self, fold):
        """加载指定折的数据"""
        train = pd.read_csv(f'{self.data_dir}/fold{fold}_train.csv')
        val = pd.read_csv(f'{self.data_dir}/fold{fold}_val.csv')

        # 分离特征和标签
        feature_cols = [col for col in train.columns if col not in ['id', 'label', 'fold']]

        X_train = train[feature_cols]
        y_train = train['label']
        X_val = val[feature_cols]
        y_val = val['label']

        return X_train, y_train, X_val, y_val, feature_cols

    def train_lightgbm(self, X_train, y_train, X_val, y_val):
        """训练 LightGBM 模型"""
        params = {
            'objective': 'multiclass' if y_train.nunique() > 2 else 'binary',
            'num_class': y_train.nunique() if y_train.nunique() > 2 else None,
            'metric': 'multi_logloss' if y_train.nunique() > 2 else 'binary_logloss',
            'boosting_type': 'gbdt',
            'learning_rate': 0.05,
            'num_leaves': 31,
            'max_depth': -1,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'seed': 42
        }

        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        model = lgb.train(
            params,
            train_data,
            num_boost_round=1000,
            valid_sets=[train_data, val_data],
            valid_names=['train', 'val'],
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)]
        )

        return model

    def train_xgboost(self, X_train, y_train, X_val, y_val):
        """训练 XGBoost 模型"""
        params = {
            'objective': 'multi:softprob' if y_train.nunique() > 2 else 'binary:logistic',
            'num_class': y_train.nunique() if y_train.nunique() > 2 else None,
            'eval_metric': 'mlogloss' if y_train.nunique() > 2 else 'logloss',
            'learning_rate': 0.05,
            'max_depth': 6,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'seed': 42,
            'tree_method': 'hist'
        }

        dtrain = xgb.DMatrix(X_train, label=y_train)
        dval = xgb.DMatrix(X_val, label=y_val)

        model = xgb.train(
            params,
            dtrain,
            num_boost_round=1000,
            evals=[(dtrain, 'train'), (dval, 'val')],
            early_stopping_rounds=50,
            verbose_eval=100
        )

        return model

    def train_catboost(self, X_train, y_train, X_val, y_val):
        """训练 CatBoost 模型"""
        model = CatBoostClassifier(
            iterations=1000,
            learning_rate=0.05,
            depth=6,
            loss_function='MultiClass' if y_train.nunique() > 2 else 'Logloss',
            eval_metric='MultiClass' if y_train.nunique() > 2 else 'Logloss',
            random_seed=42,
            early_stopping_rounds=50,
            verbose=100
        )

        model.fit(
            X_train, y_train,
            eval_set=(X_val, y_val),
            use_best_model=True
        )

        return model

    def evaluate_model(self, model, X_val, y_val, model_type):
        """评估模型"""
        if model_type == 'lightgbm':
            y_pred_proba = model.predict(X_val)
        elif model_type == 'xgboost':
            dval = xgb.DMatrix(X_val)
            y_pred_proba = model.predict(dval)
        else:  # catboost
            y_pred_proba = model.predict_proba(X_val)

        # 多分类取最大概率类别
        if y_pred_proba.ndim > 1:
            y_pred = np.argmax(y_pred_proba, axis=1)
        else:
            y_pred = (y_pred_proba > 0.5).astype(int)

        acc = accuracy_score(y_val, y_pred)
        f1 = f1_score(y_val, y_pred, average='weighted')

        return acc, f1

    def cross_validation(self, model_type='lightgbm', n_folds=5):
        """交叉验证训练"""
        print(f"\n{'='*60}")
        print(f"开始 {model_type.upper()} 交叉验证训练 ({n_folds} 折)")
        print('='*60)

        scores = []
        models = []

        for fold in range(n_folds):
            print(f"\n--- Fold {fold+1}/{n_folds} ---")

            # 加载数据
            X_train, y_train, X_val, y_val, feature_cols = self.load_fold_data(fold)

            # 训练模型
            if model_type == 'lightgbm':
                model = self.train_lightgbm(X_train, y_train, X_val, y_val)
            elif model_type == 'xgboost':
                model = self.train_xgboost(X_train, y_train, X_val, y_val)
            else:
                model = self.train_catboost(X_train, y_train, X_val, y_val)

            # 评估
            acc, f1 = self.evaluate_model(model, X_val, y_val, model_type)
            print(f"Fold {fold+1} - Accuracy: {acc:.4f}, F1: {f1:.4f}")

            scores.append({'fold': fold, 'accuracy': acc, 'f1': f1})
            models.append(model)

            # 保存模型
            if model_type == 'lightgbm':
                model.save_model(f'{self.output_dir}/{model_type}_fold{fold}.txt')
            elif model_type == 'xgboost':
                model.save_model(f'{self.output_dir}/{model_type}_fold{fold}.json')
            else:
                model.save_model(f'{self.output_dir}/{model_type}_fold{fold}.cbm')

        # 汇总结果
        scores_df = pd.DataFrame(scores)
        print(f"\n{'='*60}")
        print(f"{model_type.upper()} 交叉验证结果:")
        print(f"平均 Accuracy: {scores_df['accuracy'].mean():.4f} ± {scores_df['accuracy'].std():.4f}")
        print(f"平均 F1: {scores_df['f1'].mean():.4f} ± {scores_df['f1'].std():.4f}")
        print('='*60)

        scores_df.to_csv(f'{self.output_dir}/{model_type}_cv_scores.csv', index=False)

        return models, scores_df

    def predict_test(self, models, model_type, test_path='./processed_data/test_processed.csv'):
        """使用训练好的模型预测测试集"""
        print(f"\n{'='*60}")
        print(f"预测测试集 ({model_type.upper()})")
        print('='*60)

        test_data = pd.read_csv(test_path)
        test_ids = test_data['id']

        feature_cols = [col for col in test_data.columns if col not in ['id', 'label', 'fold']]
        X_test = test_data[feature_cols]

        # 使用所有模型预测并取平均
        predictions = []

        for i, model in enumerate(models):
            print(f"使用 Fold {i+1} 模型预测...")

            if model_type == 'lightgbm':
                pred = model.predict(X_test)
            elif model_type == 'xgboost':
                dtest = xgb.DMatrix(X_test)
                pred = model.predict(dtest)
            else:
                pred = model.predict_proba(X_test)

            predictions.append(pred)

        # 平均预测概率
        avg_pred = np.mean(predictions, axis=0)

        # 多分类取最大概率类别
        if avg_pred.ndim > 1:
            final_pred = np.argmax(avg_pred, axis=1)
        else:
            final_pred = (avg_pred > 0.5).astype(int)

        # 保存预测结果
        submission = pd.DataFrame({
            'id': test_ids,
            'label': final_pred
        })

        output_path = f'./submissions/{model_type}_submission.csv'
        os.makedirs('./submissions', exist_ok=True)
        submission.to_csv(output_path, index=False)

        print(f"✅ 预测结果已保存: {output_path}")

        return submission

if __name__ == '__main__':
    trainer = TianchiTrainer()

    # 训练三个模型
    for model_type in ['lightgbm', 'xgboost', 'catboost']:
        models, scores = trainer.cross_validation(model_type=model_type, n_folds=5)
        submission = trainer.predict_test(models, model_type)

    print("\n" + "✅ "*20)
    print("所有模型训练完成！")
    print("✅ "*20)
