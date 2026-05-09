from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing_extensions import Literal, Optional, List
from enum import Enum
class Intent(BaseModel):
    is_related: bool = Field(
        description="提问是否与系统诊断相关，相关为true,不相关为false"
    )

# 使用枚举定义健康级别
class HealthLevel(str, Enum):
    HEALTHY = "健康"
    WARNING = "警告"
    ABNORMAL = "异常"
    SEVERE = "严重"

# 使用枚举定义问题类型
class IssueType(str, Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    IO = "io"
    UNKNOWN = "unknown"

class SystemHealthReport(BaseModel):
    """系统健康状态报告"""

    health_level: HealthLevel = Field(
        description="健康级别，只能是 健康/警告/异常/严重 四选一"
    )

    has_issue: bool = Field(
        description="是否有问题，有任何告警为True，完全健康为False"
    )

    issue_type: Optional[str] = Field(
        default=None,
        description="问题类型，无问题为null，有问题则为 cpu/memory/disk/network/io/unknown 多个用英文逗号分隔"
    )

    issue_detail: str = Field(
        description="问题详情，无问题填'系统运行正常，无异常指标'，有问题则详细描述异常指标、触发阈值、影响范围"
    )

    root_cause: Optional[str] = Field(
        default=None,
        description="根因分析，无问题为null，有问题则结合top_processes分析异常根因，定位到具体进程、行为或配置问题"
    )

    commands_type: Optional[str] = Field(
        default_factory=list,
        description="字符串或null，必填，无问题为null,有问题则为 check或fix中的一个，check表示仍然需要别的参数判断系统问题，fix表示问题修复的指令"
    )

    fix_commands: List[str] = Field(
        default_factory=list,
        description="修复或者排查命令，无问题为空数组[]，有问题则给出可直接执行的Linux排查/修复命令，按优先级排序"
    )

    optimize_suggestions: str = Field(
        description="优化建议，无问题填'无需优化，继续保持'，有问题则给出长期优化建议"
    )



system_report_parser = PydanticOutputParser(pydantic_object=SystemHealthReport)
intent_parser = PydanticOutputParser(pydantic_object=Intent)
