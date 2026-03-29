/**
 * Quant Tools - 量化分析工具
 *
 * 调用 ML Pipeline 进行股票预测、回测、模型训练
 */
import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";
import { execSync } from "child_process";
import * as path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..", "..", "..");
const venvPython = path.join(projectRoot, ".venv", "bin", "python");
const mlPipeline = path.join(projectRoot, "ml-pipeline", "ml_pipeline.py");

function runMLPipeline(command: string): string {
  try {
    return execSync(`${venvPython} ${mlPipeline} ${command}`, {
      encoding: "utf-8",
      cwd: projectRoot,
      maxBuffer: 10 * 1024 * 1024,
    });
  } catch (error: any) {
    return `执行失败: ${error.message}\n${error.stdout || ""}`;
  }
}

export const predictStockSignalTool: ToolDefinition = {
  name: "predict_stock_signal",
  label: "股票信号预测",
  description: "预测股票未来5日上涨概率（基于机器学习模型）。返回上涨概率和买入/观望信号。",
  parameters: Type.Object({
    symbol: Type.String({ description: "股票代码，如 000001" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const result = runMLPipeline(`predict --symbol ${params.symbol}`);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

export const backtestStrategyTool: ToolDefinition = {
  name: "backtest_strategy",
  label: "策略回测",
  description: "回测量化策略，返回收益率、胜率、最大回撤、夏普比率等指标。用于评估策略表现。",
  parameters: Type.Object({}),
  execute: async (_toolCallId, _params: any) => {
    const result = runMLPipeline("backtest");
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

export const evaluateModelTool: ToolDefinition = {
  name: "evaluate_model",
  label: "模型评估",
  description: "评估机器学习模型性能，返回准确率、精确率、召回率、F1分数。",
  parameters: Type.Object({}),
  execute: async (_toolCallId, _params: any) => {
    const result = runMLPipeline("evaluate");
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

export const trainModelTool: ToolDefinition = {
  name: "train_model",
  label: "模型训练",
  description: "重新训练机器学习模型（耗时较长，约1-2分钟）。仅在需要更新模型时使用。",
  parameters: Type.Object({}),
  execute: async (_toolCallId, _params: any) => {
    const result = runMLPipeline("train");
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};

export const quantTools: ToolDefinition[] = [
  predictStockSignalTool,
  backtestStrategyTool,
  evaluateModelTool,
  trainModelTool,
];
