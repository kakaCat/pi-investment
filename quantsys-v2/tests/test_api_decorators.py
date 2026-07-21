"""
测试 API 装饰器
"""
import pytest
from flask import Flask, request
from adapters.inbound.api.decorators import validate_params, handle_errors, paginate
from adapters.inbound.api.validators import ValidationError
from adapters.inbound.api.response_builder import success_response, error_response


@pytest.fixture
def app():
    """创建测试Flask应用"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return app.test_client()


class TestValidateParams:
    """测试参数验证装饰器"""

    def test_required_param_missing(self, app, client):
        """测试缺少必需参数"""
        @app.route('/test')
        @validate_params({
            'name': {'type': str, 'required': True, 'source': 'args'}
        })
        def test_route(name):
            return success_response(name=name)

        response = client.get('/test')
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert '缺少必需参数' in data['error']

    def test_required_param_provided(self, app, client):
        """测试提供必需参数"""
        @app.route('/test')
        @validate_params({
            'name': {'type': str, 'required': True, 'source': 'args'}
        })
        def test_route(name):
            return success_response(name=name)

        response = client.get('/test?name=test')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['name'] == 'test'

    def test_default_value(self, app, client):
        """测试默认值"""
        @app.route('/test')
        @validate_params({
            'limit': {'type': int, 'default': 100, 'source': 'args'}
        })
        def test_route(limit):
            return success_response(limit=limit)

        response = client.get('/test')
        assert response.status_code == 200
        data = response.get_json()
        assert data['limit'] == 100

    def test_type_conversion_int(self, app, client):
        """测试整数类型转换"""
        @app.route('/test')
        @validate_params({
            'count': {'type': int, 'source': 'args'}
        })
        def test_route(count):
            return success_response(count=count, type=type(count).__name__)

        response = client.get('/test?count=42')
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 42
        assert data['type'] == 'int'

    def test_type_conversion_float(self, app, client):
        """测试浮点数类型转换"""
        @app.route('/test')
        @validate_params({
            'price': {'type': float, 'source': 'args'}
        })
        def test_route(price):
            return success_response(price=price)

        response = client.get('/test?price=12.34')
        assert response.status_code == 200
        data = response.get_json()
        assert abs(data['price'] - 12.34) < 0.001

    def test_type_conversion_bool(self, app, client):
        """测试布尔类型转换"""
        @app.route('/test')
        @validate_params({
            'active': {'type': bool, 'source': 'args'}
        })
        def test_route(active):
            return success_response(active=active)

        response = client.get('/test?active=true')
        assert response.status_code == 200
        data = response.get_json()
        assert data['active'] is True

        response = client.get('/test?active=false')
        data = response.get_json()
        assert data['active'] is False

    def test_type_conversion_list(self, app, client):
        """测试列表类型转换"""
        @app.route('/test')
        @validate_params({
            'symbols': {'type': list, 'source': 'args'}
        })
        def test_route(symbols):
            return success_response(symbols=symbols)

        response = client.get('/test?symbols=AAPL,TSLA,MSFT')
        assert response.status_code == 200
        data = response.get_json()
        assert data['symbols'] == ['AAPL', 'TSLA', 'MSFT']

    def test_min_max_validation(self, app, client):
        """测试最小最大值验证"""
        @app.route('/test')
        @validate_params({
            'age': {'type': int, 'min': 0, 'max': 150, 'source': 'args'}
        })
        def test_route(age):
            return success_response(age=age)

        # 正常值
        response = client.get('/test?age=25')
        assert response.status_code == 200

        # 小于最小值
        response = client.get('/test?age=-1')
        assert response.status_code == 400
        data = response.get_json()
        assert '不能小于' in data['error']

        # 大于最大值
        response = client.get('/test?age=200')
        assert response.status_code == 400
        data = response.get_json()
        assert '不能大于' in data['error']

    def test_length_validation(self, app, client):
        """测试长度验证"""
        @app.route('/test')
        @validate_params({
            'name': {'type': str, 'min_length': 2, 'max_length': 10, 'source': 'args'}
        })
        def test_route(name):
            return success_response(name=name)

        # 正常长度
        response = client.get('/test?name=test')
        assert response.status_code == 200

        # 太短
        response = client.get('/test?name=a')
        assert response.status_code == 400
        data = response.get_json()
        assert '长度不能小于' in data['error']

        # 太长
        response = client.get('/test?name=verylongname')
        assert response.status_code == 400
        data = response.get_json()
        assert '长度不能大于' in data['error']

    def test_choices_validation(self, app, client):
        """测试枚举值验证"""
        @app.route('/test')
        @validate_params({
            'status': {'type': str, 'choices': ['active', 'inactive', 'pending'], 'source': 'args'}
        })
        def test_route(status):
            return success_response(status=status)

        # 有效值
        response = client.get('/test?status=active')
        assert response.status_code == 200

        # 无效值
        response = client.get('/test?status=invalid')
        assert response.status_code == 400
        data = response.get_json()
        assert '必须是以下值之一' in data['error']

    def test_custom_validator(self, app, client):
        """测试自定义验证器"""
        def validate_even(value):
            if value % 2 != 0:
                raise ValidationError("必须是偶数")
            return value

        @app.route('/test')
        @validate_params({
            'number': {'type': int, 'validator': validate_even, 'source': 'args'}
        })
        def test_route(number):
            return success_response(number=number)

        # 偶数
        response = client.get('/test?number=4')
        assert response.status_code == 200

        # 奇数
        response = client.get('/test?number=3')
        assert response.status_code == 400
        data = response.get_json()
        assert '必须是偶数' in data['error']

    def test_json_params(self, app, client):
        """测试JSON参数"""
        @app.route('/test', methods=['POST'])
        @validate_params({
            'name': {'type': str, 'required': True, 'source': 'json'},
            'age': {'type': int, 'source': 'json'}
        })
        def test_route(name, age):
            return success_response(name=name, age=age)

        response = client.post('/test', json={'name': 'John', 'age': 30})
        assert response.status_code == 200
        data = response.get_json()
        assert data['name'] == 'John'
        assert data['age'] == 30

    def test_path_params(self, app, client):
        """测试路径参数"""
        @app.route('/test/<symbol>')
        @validate_params({
            'symbol': {'type': str, 'required': True, 'source': 'path'}
        })
        def test_route(symbol):
            return success_response(symbol=symbol)

        response = client.get('/test/AAPL')
        assert response.status_code == 200
        data = response.get_json()
        assert data['symbol'] == 'AAPL'


class TestHandleErrors:
    """测试错误处理装饰器"""

    def test_validation_error(self, app, client):
        """测试验证错误"""
        @app.route('/test')
        @handle_errors
        def test_route():
            raise ValidationError("参数错误")

        response = client.get('/test')
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert '参数错误' in data['error']

    def test_value_error(self, app, client):
        """测试值错误"""
        @app.route('/test')
        @handle_errors
        def test_route():
            raise ValueError("值不正确")

        response = client.get('/test')
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_file_not_found_error(self, app, client):
        """测试文件未找到错误"""
        @app.route('/test')
        @handle_errors
        def test_route():
            raise FileNotFoundError("文件不存在")

        response = client.get('/test')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    def test_generic_exception(self, app, client):
        """测试通用异常"""
        @app.route('/test')
        @handle_errors
        def test_route():
            raise Exception("未知错误")

        response = client.get('/test')
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False


class TestPaginate:
    """测试分页装饰器"""

    def test_default_pagination(self, app, client):
        """测试默认分页参数"""
        @app.route('/test')
        @paginate(default_page_size=20, max_page_size=100)
        def test_route(page, page_size, offset):
            return success_response(page=page, page_size=page_size, offset=offset)

        response = client.get('/test')
        assert response.status_code == 200
        data = response.get_json()
        assert data['page'] == 1
        assert data['page_size'] == 20
        assert data['offset'] == 0

    def test_custom_pagination(self, app, client):
        """测试自定义分页参数"""
        @app.route('/test')
        @paginate(default_page_size=20, max_page_size=100)
        def test_route(page, page_size, offset):
            return success_response(page=page, page_size=page_size, offset=offset)

        response = client.get('/test?page=3&pageSize=50')
        assert response.status_code == 200
        data = response.get_json()
        assert data['page'] == 3
        assert data['page_size'] == 50
        assert data['offset'] == 100  # (3-1) * 50

    def test_max_page_size_limit(self, app, client):
        """测试最大页面大小限制"""
        @app.route('/test')
        @paginate(default_page_size=20, max_page_size=100)
        def test_route(page, page_size, offset):
            return success_response(page=page, page_size=page_size, offset=offset)

        response = client.get('/test?pageSize=200')
        assert response.status_code == 200
        data = response.get_json()
        assert data['page_size'] == 100  # 限制为最大值

    def test_invalid_page(self, app, client):
        """测试无效页码"""
        @app.route('/test')
        @paginate(default_page_size=20, max_page_size=100)
        def test_route(page, page_size, offset):
            return success_response(page=page, page_size=page_size, offset=offset)

        response = client.get('/test?page=0')
        assert response.status_code == 200
        data = response.get_json()
        assert data['page'] == 1  # 自动修正为1


class TestDecoratorCombination:
    """测试装饰器组合使用"""

    def test_all_decorators(self, app, client):
        """测试所有装饰器组合"""
        @app.route('/test')
        @handle_errors
        @paginate(default_page_size=10, max_page_size=50)
        @validate_params({
            'q': {'type': str, 'required': True, 'min_length': 1, 'source': 'args'}
        })
        def test_route(q, page, page_size, offset):
            return success_response(
                query=q,
                page=page,
                page_size=page_size,
                offset=offset
            )

        # 成功请求
        response = client.get('/test?q=test&page=2&pageSize=20')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['query'] == 'test'
        assert data['page'] == 2
        assert data['page_size'] == 20
        assert data['offset'] == 20

        # 缺少必需参数
        response = client.get('/test')
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
