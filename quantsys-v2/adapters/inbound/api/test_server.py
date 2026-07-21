"""
最小化测试服务器 - 仅用于测试 market.news 功能
"""
import sys
from pathlib import Path

# 添加 quantsys-v2 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
from flask_cors import CORS

def create_test_app():
    app = Flask(__name__)
    CORS(app)

    # 只注册 market_bp
    from adapters.inbound.api.routes.market import market_bp
    app.register_blueprint(market_bp)

    # 健康检查
    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok', 'mode': 'test'})

    return app

if __name__ == '__main__':
    app = create_test_app()
    print("Starting test server on http://127.0.0.1:5002")
    app.run(host='127.0.0.1', port=5002, debug=False)
