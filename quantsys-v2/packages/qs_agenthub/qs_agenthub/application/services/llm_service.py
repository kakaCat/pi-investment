"""
LLM 服务薄封装（DeepSeek，OpenAI 兼容接口）
"""
import requests
import structlog
from infrastructure.config import get_config

logger = structlog.get_logger(__name__)

DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'


def chat_completion(prompt: str, model: str = 'deepseek-chat', timeout: int = 60) -> str:
    """调用 DeepSeek 返回文本内容

    Raises:
        RuntimeError: 未配置 key / 超时 / API 错误
    """
    config = get_config()
    api_key = config.external.deepseek_api_key
    if not api_key:
        raise RuntimeError('未配置 DEEPSEEK_API_KEY，无法使用 AI 诊断')

    try:
        resp = requests.post(
            DEEPSEEK_URL,
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
            },
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        raise RuntimeError('AI 诊断超时（60s），请稍后重试')
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f'AI 诊断请求失败: {e}')

    if resp.status_code != 200:
        raise RuntimeError(f'DeepSeek API 错误 {resp.status_code}: {resp.text[:200]}')

    return resp.json()['choices'][0]['message']['content']
