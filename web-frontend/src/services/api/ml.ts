import { apiClient } from './client'

// ── Request types (camelCase, converted to snake_case on wire) ──

export interface MLTrainRequest {
  modelType: 'xgboost' | 'lightgbm' | 'randomforest'
  startDate?: string
  endDate?: string
  testSize?: number
  symbols?: string[]
  params?: Record<string, any>
}

export interface MLPredictRequest {
  modelType: string
  symbols: string[]
  version?: string
}

// ── Response types (camelCase after conversion) ──

export interface MLTrainingResults {
  trainAccuracy: number
  testAccuracy: number
  precision: number
  recall: number
  f1Score: number
  featureImportance: Record<string, number>
  version: string
  modelType: string
}

export interface MLPrediction {
  symbol: string
  predictedClass: number
  probability: number
  confidence: 'high' | 'medium' | 'low'
}

export interface MLModelInfo {
  modelType: string
  version: string
  trainingDate: string
  samplesTrained: number
  accuracy: number
  featuresCount: number
  modelPath: string
}

export interface MLFeature {
  name: string
  importance: number
}

// ── API ──

export const mlApi = {
  /**
   * 训练模型
   */
  async train(params: MLTrainRequest): Promise<MLTrainingResults> {
    const res: any = await apiClient.post('/api/ml/train', {
      model_type: params.modelType,
      start_date: params.startDate,
      end_date: params.endDate,
      test_size: params.testSize ?? 0.2,
      symbols: params.symbols,
      params: params.params
    })

    const tr = res.training_results || res

    return {
      trainAccuracy: tr.train_accuracy ?? tr.trainAccuracy ?? 0,
      testAccuracy: tr.test_accuracy ?? tr.testAccuracy ?? 0,
      precision: tr.precision ?? 0,
      recall: tr.recall ?? 0,
      f1Score: tr.f1_score ?? tr.f1Score ?? 0,
      featureImportance: tr.feature_importance ?? tr.featureImportance ?? {},
      version: tr.version ?? '',
      modelType: tr.model_type ?? tr.modelType ?? params.modelType
    }
  },

  /**
   * 预测
   */
  async predict(params: MLPredictRequest): Promise<MLPrediction[]> {
    const res: any = await apiClient.post('/api/ml/predict', {
      model_type: params.modelType,
      symbols: params.symbols,
      version: params.version || 'latest'
    })

    const predictions: any[] = res.predictions || res || []

    return predictions.map((p: any) => ({
      symbol: p.symbol ?? '',
      predictedClass: p.predicted_class ?? p.predictedClass ?? 0,
      probability: p.probability ?? 0,
      confidence: p.confidence ?? 'low'
    }))
  },

  /**
   * 获取模型信息
   */
  async getModelInfo(modelType: string): Promise<MLModelInfo | null> {
    const res: any = await apiClient.get('/api/ml/model/info', {
      params: { model_type: modelType }
    })

    const info = res.model_info || res
    if (!info || (typeof info === 'object' && Object.keys(info).length === 0)) {
      return null
    }

    return {
      modelType: info.model_type ?? info.modelType ?? modelType,
      version: info.version ?? '',
      trainingDate: info.training_date ?? info.trainingDate ?? '',
      samplesTrained: info.samples_trained ?? info.samplesTrained ?? 0,
      accuracy: info.accuracy ?? 0,
      featuresCount: info.features_count ?? info.featuresCount ?? 0,
      modelPath: info.model_path ?? info.modelPath ?? ''
    }
  },

  /**
   * 获取特征重要性
   */
  async getFeatures(modelType?: string): Promise<MLFeature[]> {
    const res: any = await apiClient.get('/api/ml/features', {
      params: modelType ? { model_type: modelType } : {}
    })

    const features: any[] = res.features || res || []

    return features.map((f: any) => ({
      name: f.name ?? '',
      importance: f.importance ?? 0
    }))
  }
}
