import sys
sys.path.insert(0, '.')
import os
os.environ['PGDATABASE'] = 'quant_investment'
os.environ['PGHOST'] = '127.0.0.1'
os.environ['PGPORT'] = '5432'
os.environ['PGUSER'] = 'mac'

# 添加调试钩子
import application.services.technical_analysis_service as tas_module
original_calculate_buy_range = tas_module.TechnicalAnalysisService.calculate_buy_range

def debug_calculate_buy_range(self, symbol):
    print(f"[DEBUG] calculate_buy_range called with symbol={symbol}")
    result = original_calculate_buy_range(self, symbol)
    print(f"[DEBUG] calculate_buy_range returned: success={result.get('success')}, error={result.get('error')}")
    return result

tas_module.TechnicalAnalysisService.calculate_buy_range = debug_calculate_buy_range

# 现在测试路由
from flask import Flask
from adapters.inbound.api.routes.analysis import analysis_bp

app = Flask(__name__)
app.register_blueprint(analysis_bp)

with app.test_client() as client:
    print("\n=== Testing with Flask test client ===")
    response = client.get('/api/stock/600000/buy-range')
    print(f"Status: {response.status_code}")
    print(f"Response: {response.get_json()}")

print("\n=== Testing direct service call ===")
from application.services.technical_analysis_service import TechnicalAnalysisService
service = TechnicalAnalysisService()
result = service.calculate_buy_range('600000')
print(f"Direct result: {result}")
