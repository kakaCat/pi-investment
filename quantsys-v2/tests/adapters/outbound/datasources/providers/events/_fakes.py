"""事件 provider 测试共用：不触网的假 requests.Session（各 provider 用 monkeypatch 注入）"""


class FakeResponse:
    def __init__(self, payload=None, *, status=200, text='', content=b'', json_error=False):
        self._payload = payload
        self.status_code = status
        self.text = text
        self.content = content
        self.encoding = None
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError('No JSON object could be decoded')
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


class FakeSession:
    """按调用顺序返回预设响应；记录全部调用参数供断言（不触网）"""

    def __init__(self, responses):
        self.responses = list(responses) if isinstance(responses, (list, tuple)) else [responses]
        self.calls = []

    def _next(self, url, kwargs):
        self.calls.append({'url': url, **kwargs})
        if not self.responses:
            raise AssertionError('FakeSession 收到的调用次数超过预设响应数（测试未覆盖该路径）')
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        return self._next(url, kwargs)

    def post(self, url, **kwargs):
        return self._next(url, kwargs)


def patch_session(monkeypatch, module, fake):
    monkeypatch.setattr(module, '_session', lambda: fake, raising=False)
    return fake


class FakeFrame:
    """akshare 返回值的最小替身（provider 只用到 columns / to_dict('records')）"""

    def __init__(self, columns, records):
        self.columns = list(columns)
        self._records = list(records)

    def to_dict(self, orient='records'):
        assert orient == 'records'
        return list(self._records)
