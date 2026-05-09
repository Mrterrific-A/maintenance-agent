from typing_extensions import Literal,Dict,Annotated, TypedDict, Optional, List
from langchain.messages import AnyMessage
import operator


class MemoryState(TypedDict):
    """内存情况"""
    memory_total: int
    memory_available: int
    memory_used: int
    memory_percent: int
    swap_total: int
    swap_used: int
    swap_percent: int


class CpuState(TypedDict):
    """cpu情况"""
    total: float
    per_cpu: float
    user: float
    system: float
    idle: float
    iowait: float
    irq: float
    softirq: float

class DiskPartitionInfo(TypedDict):
    """单个磁盘分区的信息"""
    total: int
    used: int
    free: int
    percent: float
    device: str
    fstype: str

# 【新增】磁盘使用情况结构（外层：挂载点 -> 分区信息）
class DiskUsageState(TypedDict):
    """所有磁盘分区的使用情况，键为挂载点"""
    __root__: Dict[str, DiskPartitionInfo]

class DiskIOState(TypedDict):
    """磁盘IO情况"""
    read_count: int
    write_count: int
    read_bytes: int
    write_bytes: int
    read_time: int
    write_time: int

class NetworkIOState(TypedDict):
    """网络IO情况"""
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int


class SystemLoadState(TypedDict):
    """系统负载情况"""
    min_1:float
    min_5: float
    min_15: float

class CommandFix(TypedDict):
    """修复指令以及执行情况"""
    command: str
    success: bool
    output: str

class CommandFurtherCheck(TypedDict):
    command: str
    returncode: int
    stdout: str
    stderr: str


class SystemState(TypedDict):
    """系统监测数据"""

    # 消息
    messages: Annotated[List[AnyMessage], operator.add]
    # 意图识别
    is_related: bool
    # 检查次数
    further_check_count:int
    # cpu利用率
    cpu_usage: CpuState
    # 内存利用率
    mem_usage: MemoryState
    # 磁盘利用率
    disk_usage: DiskUsageState
    # 磁盘IO
    disk_io: DiskIOState
    # 网络IO
    network_io: NetworkIOState
    # 系统负载
    system_load: SystemLoadState

    # 使用率前三进程
    # top_processes: List[dict]
    # 问题分析
    has_issue: bool
    issue_type: Optional[str]  # "cpu", "memory", "disk", "unknown"
    issue_detail: Optional[str]

    # 进一步诊断信息
    further_check: Optional[List[CommandFurtherCheck]]

    # 修复方案
    root_cause: Optional[str]
    commands_type: Optional[str]
    fix_commands: Optional[List[str]]

    # 人工确认
    human_approved: Optional[List[str]]
    human_feedback: Optional[str]

    # 执行结果
    fix_result: Optional[List[CommandFix]]



class CommandState(TypedDict):
    command: str
    is_sensitive: bool
    confirmed: Optional[bool]
    success: bool
    output: str