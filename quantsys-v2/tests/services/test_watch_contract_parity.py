"""判据文档 ↔ 代码码表同源对拍（REQ-261007133807-eda6 t12 · FR-5）

为什么要有这个文件：文档一旦成为**第二份事实源**就会说假话——本需求立项时的取证就是
`opportunity_to_watch_rule_service.py` 仍写着「触发频率异常时升级L2」，而那条路径早在
REQ-c9f899 t7 已删除。判据表与码表必须机械对拍，而不是靠人记得同步。

守四件事：
1) 契约文档 §6 判据表与 `EscalationCode.ALL` 逐码一致（码集合 + 叫/不叫）；
2) 设计文档 data-model.md 的码表也与代码一致（两份文档 + 代码三方同源）；
3) **正则必须容忍数字**（`RULE_LEVEL_L2` 的 `2`）——实测过一次：`[A-Z_]+` 把该码
   静默漏掉，对拍"通过"却是假绿。此处显式断言该码在解析结果里；
4) 已删路径的陈旧表述在 application / domain / docs/architecture 下**零命中**。
"""
import os
import re

from domain.watch.services.escalation_verdict import EscalationCode

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONTRACT = os.path.join(REPO, 'docs/architecture/watch-notification-contract.md')
DATA_MODEL = os.path.join(REPO, 'docs/requirements/REQ-261007133807-eda6/design/data-model.md')

_CODE_CELL = re.compile(r'^`([A-Z][A-Z0-9_]{2,})`$')


def _parse_code_table(path):
    """解析「| `CODE` | 语义 | ✅/❌ | ...」形态的码表 → {code: 是否叫 agent}。

    刻意**不写死列序**（只认首列的受控码与行内任一 ✅/❌ 列），这样两张文档的
    表结构可以各自演进，但只要码与叫/不叫能读出来就必须与代码一致。
    """
    codes = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            if not line.startswith('|'):
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if not cells:
                continue
            m = _CODE_CELL.match(cells[0])
            if m is None:
                continue
            flag = next((c for c in cells if c in ('✅', '❌')), None)
            if flag is not None:
                codes[m.group(1)] = (flag == '✅')
    return codes


def test_contract_doc_code_table_matches_code():
    parsed = _parse_code_table(CONTRACT)
    assert parsed, '契约文档里没解析到判据表（表结构或被改坏）'
    # ① 数字码必须被解析到（正则写窄会静默漏掉，曾实测）
    assert 'RULE_LEVEL_L2' in parsed
    # ② 码集合与叫/不叫集合逐条一致
    assert set(parsed) == set(EscalationCode.ALL), set(parsed) ^ set(EscalationCode.ALL)
    waking = {c for c, wakes in parsed.items() if wakes}
    assert waking == set(EscalationCode.WAKING), waking ^ set(EscalationCode.WAKING)


def test_design_doc_code_table_matches_code():
    parsed = _parse_code_table(DATA_MODEL)
    assert parsed, '设计文档里没解析到码表'
    assert set(parsed) == set(EscalationCode.ALL)
    assert {c for c, w in parsed.items() if w} == set(EscalationCode.WAKING)


def test_two_docs_agree_with_each_other():
    """两份文档必须互相一致——只对代码不对文档的话，任一份都能悄悄漂走。"""
    assert _parse_code_table(CONTRACT) == _parse_code_table(DATA_MODEL)


def test_removed_path_text_is_gone_from_live_docs_and_code():
    """已删除的历史升级路径不得再被写成现行规则（本需求立项的直接动因）。"""
    stale = ('触发频率异常', '触发频率升级')
    offenders = []
    for root in ('application', 'domain', 'docs/architecture'):
        for dirpath, _dirnames, filenames in os.walk(os.path.join(REPO, root)):
            if '__pycache__' in dirpath:
                continue
            for name in filenames:
                if not name.endswith(('.py', '.md')):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    text = open(path, encoding='utf-8').read()
                except (OSError, UnicodeDecodeError):
                    continue
                for phrase in stale:
                    if phrase in text:
                        # 严格零命中（FR-5 判据 6）：连"历史说明"里也不留该字面串——
                        # 说明改写为「触发频率」异常，既保留来龙去脉，又不让 grep 判据失效。
                        offenders.append('%s: %s' % (os.path.relpath(path, REPO), phrase))
    assert not offenders, offenders
