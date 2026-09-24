"""
Watch 领域端口（接口定义）

定义 WatchEngine 核心领域的抽象接口，由基础设施层实现。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime

from domain.watch.models import WatchRule, RuleHealthReport


class IWatchRuleRepository(ABC):
    """盯盘规则仓储接口"""
    
    @abstractmethod
    def get_all_enabled(self) -> List[WatchRule]:
        """获取所有启用的规则"""
        pass
    
    @abstractmethod
    def get_by_id(self, rule_id: int) -> Optional[WatchRule]:
        """根据 ID 获取规则"""
        pass
    
    @abstractmethod
    def get_by_symbol(self, symbol: str) -> List[WatchRule]:
        """根据股票代码获取规则"""
        pass
    
    @abstractmethod
    def update(self, rule: WatchRule) -> bool:
        """更新规则"""
        pass
    
    @abstractmethod
    def disable(self, rule_id: int, reason: str) -> bool:
        """禁用规则"""
        pass


class ITriggerHistoryRepository(ABC):
    """触发历史仓储接口"""
    
    @abstractmethod
    def count_recent_triggers(self, rule_id: int, window_minutes: int) -> int:
        """统计规则近 window_minutes 分钟内的触发次数"""
        pass
    
    @abstractmethod
    def count_concurrent_triggers(self, symbol: str, window_seconds: int) -> int:
        """统计股票近 window_seconds 秒内的并发触发规则数"""
        pass
    
    @abstractmethod
    def get_last_trigger(self, rule_id: int) -> Optional[datetime]:
        """获取规则最后一次触发时间"""
        pass


class IQuoteProvider(ABC):
    """实时行情端口"""
    
    @abstractmethod
    def get_current_price(self, symbol: str) -> Optional[float]:
        """获取股票当前价格"""
        pass


class IWatchDigestStateRepository(ABC):
    """盯盘摘要状态端口（REQ-f08def P4）

    摘要门的"上次唤醒时间/当日唤醒次数"必须落库——存进程内存会在重启后清零，
    使每日预算形同虚设（2026-09-11 实测）。
    """

    @abstractmethod
    def load_state(self) -> Any:
        """返回 {last_wake_at, wake_date, wake_count}"""
        pass

    @abstractmethod
    def save_wake(self, now: datetime) -> None:
        """记录一次唤醒（当日计数自增，跨日归零）"""
        pass


class IWatchInterventionRepository(ABC):
    """介入记账端口（REQ-f08def P4）

    agent 每被唤醒介入一次都要留痕：规则/标的/意图/类型/结果/成本/审计 id；
    并提供当日计数与"单位唤醒产出"口径。
    """

    @abstractmethod
    def count_today(self) -> int:
        pass

    @abstractmethod
    def record(self, symbol: str, intent: Optional[str] = None, rule_id: Optional[int] = None,
               trigger_kind: str = "price", outcome: str = "escalated",
               trigger_ids: Optional[List[int]] = None, tokens: Optional[int] = None,
               cost_yuan: float = 0.0, decision_audit_id: Optional[str] = None) -> None:
        pass

    @abstractmethod
    def summary_today(self) -> Any:
        pass



class IMarketStateProvider(ABC):
    """市场状态端口（REQ-f08def P6，RFC 014 v3 §1.1/§8）

    市场级盯盘（指数/涨停家数/情绪/量能/板块）与个股盯盘的数据来源完全不同：
    前者靠市场级快照，后者靠个股实时报价。取数实现放适配器层，应用/领域层只认本端口。
    """

    @abstractmethod
    def get_state(self):
        """返回 domain.watch.models.MarketState（缺数据项记入 degraded，不得用 0 冒充）"""
        pass


class IWatchRuntimeStateStore(ABC):
    """盯盘运行态持久化端口（REQ-c9f899 R10，2026-09-18）

    为什么必须落库：闩锁与冷却基准原先只存进程内存，重启即丢——实测单日触发
    23 次 > 1800s 冷却理论上限 16 次，冷却形同虚设。本端口让「冷却是真的」。

    契约：
      · 主键 (rule_id, cond_idx)：同一规则的多条件各自闩锁/冷却；
      · 实现放 adapters/outbound/repositories（ADR-001：SQL 只在适配器层）；
      · **失败必须向上抛**（读/写皆然）：消费方（StateManager）要能感知冷却基准
        丢失并置 degraded，禁止静默降级为"未闩锁/无冷却"（那正是本次要修的 bug）。

    注意：本端口只负责闩锁与冷却基准；去重窗/价格历史不在 t3 范围。
    """

    @abstractmethod
    def load_all(self) -> List[Dict[str, Any]]:
        """返回全部运行态行。

        每行：{rule_id: int, cond_idx: int, latched: bool,
               last_triggered_at: datetime | None, cooldown_effective_sec: int | None}
        """
        pass

    @abstractmethod
    def upsert_many(self, rows: List[Dict[str, Any]]) -> None:
        """批量 upsert（冲突键 (rule_id, cond_idx)）；失败抛错"""
        pass

    @abstractmethod
    def load_meta(self) -> Dict[str, Any]:
        """返回单行 meta：{heartbeat_at, state_date, event_watermark}；无记录时值为 None"""
        pass

    @abstractmethod
    def save_meta(self, **fields: Any) -> None:
        """upsert 单行 meta（恒 id=1），只更新传入字段；失败抛错"""
        pass

# ── 盯盘待办闭环（REQ-c9f899 t5，2026-09-18）────────────────────────────────
#: 待办终态（interfaces.md §1.1：terminal ∈ (handled, ignored, expired)）；I3「必有终态」
TODO_TERMINALS = ('handled', 'ignored', 'expired')

#: 关闭时**必须**带 decision_audit_id 的动作类型（I4：动作类关单必须可核验）
TODO_AUDIT_ACTION_KINDS = ('trade', 'rule_change')

#: 允许写入 quant.watch_todos.autonomy 的值（与 DB CHECK 一致）。
#: ⚠️ 策略账户经 WatchDeliveryPolicy.resolve_autonomy 返回 not_applicable，**不符合 DB CHECK**——
#: TodoService 必须以 route_owner(...).out_of_scope 为跳过信号，不得为其建待办（t4 任务卡提醒）。
TODO_ALLOWED_AUTONOMY = ('autonomous', 'remind_only')

#: 流转态（L1 通知 → L2 待办 → L3 处置）
TODO_FLOW_STATES = ('L1', 'L2', 'L3')


class WatchTodoError(Exception):
    """盯盘待办领域错误基类

    每个子类的 code 与 interfaces.md §4 的错误码一一对应；**HTTP 状态码的映射留在
    路由/适配器层**（domain 不感知 HTTP）——领域只负责给出稳定、可判别的错误码。

    为什么要有这组异常：终态校验（I3/I4）是**领域规则**而非接口细节；用返回值表达
    「invalid terminal / already closed / missing audit」会让调用方各自解释（第二份真相），
    且路由层无法把 400 与 409 分开。显式异常让「拒绝原因」不可被静默忽略。
    """
    code = 'watch_todo_error'

    def __init__(self, message: str = ''):
        self.message = message or self.code
        super().__init__(self.message)


class WatchTodoNotFound(WatchTodoError):
    """待办不存在（404 watch_todo_not_found）"""
    code = 'watch_todo_not_found'


class WatchTodoAlreadyClosed(WatchTodoError):
    """已终态再次关闭/认领（409 watch_todo_already_closed；I3 终态唯一）"""
    code = 'watch_todo_already_closed'


class WatchTodoInvalidTerminal(WatchTodoError):
    """terminal 不在枚举内（400 watch_todo_invalid_terminal）"""
    code = 'watch_todo_invalid_terminal'


class WatchTodoMissingAudit(WatchTodoError):
    """L3 的 trade/rule_change 关闭缺 decision_audit_id（400 watch_todo_missing_audit；I4）"""
    code = 'watch_todo_missing_audit'


class WatchTodoMissingNextCondition(WatchTodoError):
    """ignored 未给 NEXT 条件（400 watch_todo_missing_next_condition；I4 拒绝也要给 NEXT）"""
    code = 'watch_todo_missing_next_condition'


class WatchTodoOutOfScope(WatchTodoError):
    """策略账户盯盘不介入（out_of_scope）——不得建待办

    复用 domain.watch.services.owner_router.route_owner 的判定；策略账户的交易由策略引擎
    执行，与盯盘无关（用户 2026-09-11）。注意其 autonomy='not_applicable' 也不符合
    quant.watch_todos.autonomy 的 DB CHECK，因此这里必须是**拒绝**而非改写 autonomy。
    """
    code = 'watch_todo_out_of_scope'


class WatchTodoInvalidAutonomy(WatchTodoError):
    """autonomy 超出 DB CHECK 允许集（400 watch_todo_invalid_autonomy）

    防守型校验：route_owner 正常路径只产出 autonomous/remind_only（策略账户已由
    out_of_scope 先拦），此异常用于「不该发生但若发生必须响亮失败」的场景——
    绝不允许静默把 not_applicable 改写成 remind_only 落库（那会让策略账户凭空产生待办）。
    """
    code = 'watch_todo_invalid_autonomy'


class IWatchTodoRepository(ABC):
    """盯盘待办仓储端口（REQ-c9f899 R2 闭环，interfaces.md §2）

    职责：quant.watch_todos 的读写。**SQL 只在适配器层**（ADR-001），本端口不含任何
    ORM/SQLAlchemy 类型——实现返回的记录对象按属性 duck-typed 访问
    （id / trigger_id / rule_id / symbol / account / level / flow_state / owner_kind /
     owner_ref / autonomy / sla_seconds / due_at / claimed_at / closed_at / terminal /
     close_reason / next_condition / action_kind / decision_audit_id / escalate_count）。

    关键语义（与 data-model.md §2 的约束互为双保险）：
      · **claim 只在未终态时生效**：已终态（terminal 非空）返回 None，绝不改行；
        认领同时把 L1 通知推进到 L2 待办（R2：L1 的退出条件 = 有人认领）。
      · **close 只写终态字段**：terminal / closed_at / close_reason / next_condition /
        action_kind / decision_audit_id（+updated_at）；不改 symbol/level/owner 等身份列。
        已终态（或并发抢先收敛）返回 None，绝不二次改写（I3）。
      · **list_overdue** 只取 (terminal IS NULL AND due_at < now)，命中
        idx_watch_todos_overdue(terminal, due_at) —— 巡检任务的唯一扫描口径（I1）。
      · **promote** 只对未终态行生效：置新 flow_state 并累加 escalate_count（缺省 +1）。
      · **list_pending** 缺省只返回未收敛待办（对齐 §2 语义）；额外可选 flow_state /
        terminal 过滤供 GET /api/watch/todos（interfaces §1.1）使用（additive）。

    失败语义：**读写失败一律向上抛**（与 IWatchRuntimeStateStore 同纪律）。静默返回
    空列表会让「查询坏了」伪装成「没有待办」，使 I1 的巡检看起来正常却漏晋升。
    """

    @abstractmethod
    def create(self, symbol: str, *, rule_id: Optional[int] = None,
               trigger_id: Optional[int] = None, account: Optional[str] = None,
               level: str, flow_state: str = 'L1', owner_kind: Optional[str] = None,
               owner_ref: Optional[str] = None, autonomy: Optional[str] = None,
               sla_seconds: int, due_at: datetime,
               action_kind: Optional[str] = None) -> Any:
        """落一条待办；返回落库后的记录。失败抛错。"""
        pass

    @abstractmethod
    def get(self, todo_id: int) -> Optional[Any]:
        """按 id 取待办；不存在返回 None。"""
        pass

    @abstractmethod
    def claim(self, todo_id: int, owner_ref: str, *, now: Optional[datetime] = None) -> Optional[Any]:
        """认领待办（owner_ref + claimed_at，L1→L2）。

        返回认领后的记录；**已是终态（或不存在该未终态行）返回 None**——调用方据 None
        映射 409/404，绝不静默成功。
        """
        pass

    @abstractmethod
    def close(self, todo_id: int, terminal: str, *, close_reason: Optional[str] = None,
              next_condition: Optional[str] = None, action_kind: Optional[str] = None,
              decision_audit_id: Optional[str] = None, closed_by: Optional[str] = None,
              now: Optional[datetime] = None) -> Optional[Any]:
        """收敛待办（写终态字段）。

        返回收敛后的记录；**已是终态（或并发抢先）返回 None**，绝不二次改写。
        closed_by：关闭者身份（供审计/日志；data-model 的 watch_todos 无该列，见实现说明）。
        """
        pass

    @abstractmethod
    def list_overdue(self, now: Optional[datetime] = None, limit: int = 100) -> List[Any]:
        """巡检查询：非终态且 due_at < now（now 缺省用数据库时钟 NOW()），按 due_at 升序。"""
        pass

    @abstractmethod
    def promote(self, todo_id: int, to_state: str, *,
                escalate_count: Optional[int] = None,
                now: Optional[datetime] = None) -> Optional[Any]:
        """晋升流转态（L1→L2→L3）。仅对未终态行生效；escalate_count 缺省自增 1。"""
        pass

    @abstractmethod
    def list_pending(self, level: Optional[str] = None, account: Optional[str] = None,
                     limit: int = 100, *, flow_state: Optional[str] = None,
                     terminal: Optional[str] = None) -> List[Any]:
        """列出待办。缺省只含未收敛（terminal IS NULL）；terminal='*' 表示不过滤终态。"""
        pass


# ── 盯盘回执（REQ-c9f899 t6，2026-09-18）──────────────────────────────────
#: 回执类型（与 migration 20260918_watch_todo_loop.py 的 watch_receipts.kind CHECK 一致）：
#: escalate=升级即 / result=处置后 / timeout=超时升级给用户 / suppressed=抑噪通知。
RECEIPT_KINDS = ('escalate', 'result', 'timeout', 'suppressed')


class IWatchReceiptRepository(ABC):
    """盯盘回执仓储端口（REQ-c9f899 t6；data-model.md §5 的 quant.watch_receipts）

    职责：回执台账的**追加写 + 幂等查询**。回执三段（R5/成功标准 8）：
      escalate（升级即：已交 agent / 已通知你 + SLA）/ result（处置后：结论 + 动作或 NEXT）/
      timeout（超时：升级给你本人）。

    **幂等键 = (todo_id, kind, payload_digest)**：payload_digest 是渲染输入摘要
    （见 application/services/watch_engine/receipt_service.payload_digest），同一待办同一
    due 周期内的同一条回执只会落一条、只发一次——这是「反复触发不刷屏」的机械保证。
    因此 record 的 payload_digest **不可为空**（空 digest 让幂等退化为"每次都是新回执"）。

    实现放 adapters/outbound/repositories（ADR-001：SQL 只在适配器层）。
    失败语义与 IWatchTodoRepository 同纪律：**写入/查询失败一律向上抛**——静默返回
    False 会把"回执库坏了"伪装成"这条回执已经发过了"，正是要避免的假成功。
    """

    @abstractmethod
    def record(self, todo_id: int, kind: str, channel: Optional[str] = None,
               delivery_status: Optional[str] = None, message_id: Optional[str] = None,
               payload_digest: str = '') -> Any:
        """落一条回执；返回落库后的记录。失败抛错。

        channel          逻辑频道码（如 alerts / reports）。
        delivery_status  sent / failed / log_only（未接线时只记日志，绝不当成 sent）。
        message_id       与 notification_logs 关联的外发消息 id（可选）。
        payload_digest   **必填**（实现须对空值响亮拒绝）；幂等去重键的一部分。
        """
        pass

    @abstractmethod
    def list_by_todo(self, todo_id: int) -> List[Any]:
        """按待办取全部回执（时间升序），供追溯「升级即 → 处置后」两段链。失败抛错。"""
        pass

    @abstractmethod
    def exists(self, todo_id: int, kind: str, payload_digest: str) -> bool:
        """幂等查询：同一待办 + 类型 + 摘要是否已落过回执。失败抛错（不得静默 False）。"""
        pass


# ── 标的名解析（REQ-260924104605-ad0a t1，2026-09-24）────────────────────────
class StockNameResolver(ABC):
    """标的名解析端口：symbol → 名称**批量**解析（quant.stocks 只读联查）。

    为什么批量：SLA 巡检一轮可能有几十条到期待办，逐条打 DB 是 N+1；
    渲染方（回执/聚合卡）在渲染前一次性 resolve_batch，注入各条目。

    降级纪律（R-013）：未命中返回 None——调用方如实降级为「代码（名称缺失）」，
    **绝不臆造名称**；实现侧查询异常也不许抛进巡检主循环（返回全 None）。
    实现放 adapters/outbound/repositories（ADR-001：SQL 只在适配器层）。
    """

    @abstractmethod
    def resolve_batch(self, symbols: List[str]) -> Dict[str, Optional[str]]:
        """批量解析名称。键 = 规范化后的 6 位 symbol（输入可带 .SH/.SZ 后缀）；
        未命中值为 None。查询异常 → 返回全 None（记日志），不抛错。"""
        pass


# ── 盯盘规则自愈（REQ-c9f899 R6 / t8，2026-09-18）────────────────────────────
#: 规则变更动作全集（= domain/watch/services/noise_policy.CHANGE_KINDS；此处只作文档引用，
#: 不 import 以免端口模块对具体策略模块产生依赖）。
#:   REPAIR_ACTIONS = cooldown / threshold / split / merge / retire
#:   + 抑噪态两动作：suppress / unsuppress
#: 与 data-model.md §4 的 watch_rule_changes.change_kind 一一对应。


class WatchRuleChangeError(Exception):
    """规则变更领域错误基类（HTTP 状态映射留在路由层，domain 不感知 HTTP）

    与 WatchTodoError 同纪律：拒绝原因必须用**显式异常**表达，不允许用返回值各自解释
    （那会催生第二份真相，且路由层无法把 400/403/404 分开）。
    """
    code = 'watch_rule_change_error'

    def __init__(self, message: str = ''):
        self.message = message or self.code
        super().__init__(self.message)


class WatchRuleChangeUnauthorized(WatchRuleChangeError):
    """用户账户规则被 agent 直接变更（403 watch_rule_change_unauthorized）

    依据 R3/I5：agent 自有账户的规则 agent 可自主修改并留痕；**用户账户（或未登记账户）
    的规则只提请，必须用户本人确认**——"改规则"与"下单"同档授权，不能被绕过。
    """
    code = 'watch_rule_change_unauthorized'


class WatchRuleChangeInvalidKind(WatchRuleChangeError):
    """change_kind 不在允许集合内（400 watch_rule_change_invalid_kind）"""
    code = 'watch_rule_change_invalid_kind'


class WatchRuleChangeMissingReason(WatchRuleChangeError):
    """缺少变更理由（400 watch_rule_change_missing_reason）

    理由必填的理由与 R-020 同源：规则变更必须可回溯"为什么改"，否则无法复盘、无法反向应用。
    """
    code = 'watch_rule_change_missing_reason'


class WatchRuleChangeRuleNotFound(WatchRuleChangeError):
    """规则不存在（404 watch_rule_change_rule_not_found）"""
    code = 'watch_rule_change_rule_not_found'


class IWatchRuleChangeRepository(ABC):
    """规则变更审计仓储端口（REQ-c9f899 R6；data-model.md §4 的 quant.watch_rule_changes）

    职责：**追加写**规则变更台账 + 幂等查询。审计表只增不改（可反向应用），因此没有
    update/delete。

    契约：
      · record 的 reason **必填非空**——理由缺失时实现必须响亮抛错（空理由让"为什么改"
        永久丢失，比不写这条记录更糟）；
      · change_kind 由调用方（应用层）按 noise_policy.CHANGE_KINDS 校验；
      · exists_since 是**自愈日幂等**的判据：同一规则同一日已有一条 suppress 变更 ⇒
        scan 不再重复建「修规则」待办（见 NoiseSelfHealService.scan）；
      · 失败语义与其它盯盘端口一致：**读写失败一律向上抛**——静默返回 None/False 会把
        "审计库坏了"伪装成"没记过/记成功了"。

    实现放 adapters/outbound/repositories（ADR-001：SQL 只在适配器层）。
    """

    @abstractmethod
    def record(self, rule_id: int, changed_by: str, change_kind: str, before: Any = None,
               after: Any = None, reason: str = '', trigger_id: Optional[int] = None,
               todo_id: Optional[int] = None,
               decision_audit_id: Optional[str] = None) -> Any:
        """追加写一条规则变更；返回落库后的记录。reason 空 → 抛错。"""
        pass

    @abstractmethod
    def exists_since(self, rule_id: int, change_kind: str, since: datetime) -> bool:
        """该规则自 since 起是否已有某类变更（自愈日幂等判据）。失败抛错。"""
        pass

    @abstractmethod
    def list_by_rule(self, rule_id: int, limit: int = 50) -> List[Any]:
        """按规则取变更历史（时间倒序）；失败抛错。"""
        pass


class IWatchRuleNoiseRepository(ABC):
    """规则抑噪态 + 触发日聚合端口（REQ-c9f899 R6 / t8）

    为什么单独成端口（而非塞进 IWatchRuleRepository / IWatchRuleChangeRepository）：
    t8 需要 ① watch_rules 的 noise_state/suppress_until/self_heal_count/last_repair_at 四列
    的读写（t1 迁移已加）与 ② watch_triggers 的按日聚合；前者属规则本仓、后者属触发本仓，
    而现有 WatchRuleRepository 未声明这四列（ORM 映射不在 t8 允许改动的文件内），
    把它塞进"规则变更审计"端口又会把两张表混成一个职责。故单列本端口，由
    adapters/outbound/repositories/watch_rule_noise_repository.py 实现（ADR-001）。

    契约：
      · get_rule 返回**最小投影**（id/symbol/account/linked_account + 四个 noise 列），
        按属性或 dict 访问皆可（实现用 dict，见适配器 docstring）；
      · daily_counts 只做**事实聚合**，连续天数/日均的解释权在 domain
        （noise_policy.consecutive_active_days / average_per_active_day），避免 SQL 里出现
        第二份阈值口径；
      · mark_suppressed 置 noise_state='suppressed' + suppress_until 并累加 self_heal_count；
      · mark_repaired 清抑噪态（noise_state/suppress_until 置空）+ 记 last_repair_at +
        累加 self_heal_count；
      · 失败语义同其它端口：读写失败一律向上抛。
    """

    @abstractmethod
    def get_rule(self, rule_id: int) -> Optional[Any]:
        """规则最小投影；不存在返回 None。"""
        pass

    @abstractmethod
    def daily_counts(self, since: datetime, until: datetime) -> Dict[int, Dict[Any, int]]:
        """[since, until) 内按规则 × 自然日聚合触发次数：{rule_id: {date: count}}"""
        pass

    @abstractmethod
    def mark_suppressed(self, rule_id: int, suppress_until: datetime,
                        now: Optional[datetime] = None) -> None:
        """置抑噪态（noise_state='suppressed' + suppress_until + self_heal_count+1）"""
        pass

    @abstractmethod
    def mark_repaired(self, rule_id: int, now: Optional[datetime] = None) -> None:
        """清抑噪态并记一次修复（noise_state=NULL, suppress_until=NULL, last_repair_at=now）"""
        pass


