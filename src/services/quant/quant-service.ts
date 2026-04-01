import { execSync } from 'child_process';

export class QuantService {
  train(): string {
    return execSync('python ml-pipeline/ml_pipeline.py train', { encoding: 'utf-8' });
  }

  predict(symbol: string): string {
    return execSync(`python ml-pipeline/ml_pipeline.py predict --symbol ${symbol}`, { encoding: 'utf-8' });
  }

  backtest(): string {
    return execSync('python ml-pipeline/ml_pipeline.py backtest', { encoding: 'utf-8' });
  }

  backtestStrategy(name: string): string {
    return execSync(`python ml-pipeline/ml_pipeline.py backtest --strategy ${name}`, { encoding: 'utf-8' });
  }
}
