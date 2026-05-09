from tempfile import template

from langchain_core.messages import SystemMessage
from langchain_core.prompts.chat import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from utils.parser import system_report_parser, intent_parser

intent_prompts = """
你是一个用于 LangGraph 意图识别的二分类器。你的唯一任务：判断用户输入的文本是否与 Linux 系统的运行状态相关。如果相关，只输出单词 True；如果不相关，只输出单词 False。不要输出任何其他解释、标点或空格。

“与 Linux 系统运行状态相关” 包括但不限于：
- 查询或操作系统的整体运行情况（如负载、运行时间、用户数）
- 进程信息（查看、启动、停止、杀死进程，如 ps, top, kill）
- CPU / 内存 / 磁盘 / 网络的使用率、瓶颈、统计信息（如 free, df, netstat, iostat）
- 系统服务或守护进程的状态（如 systemctl status）
- 查看或分析系统日志（如 dmesg, journalctl, /var/log/ 下的内容）
- 内核信息、中断、模块加载状态（如 lsmod, uname）
- 硬件资源状态（如温度、风扇转速、磁盘健康）
- 性能监控、故障排查、资源限制（如 ulimit, cgroups）
- 计划任务（cron）或系统定时器的运行情况
- 系统安全状态（如 fail2ban 状态、登录记录、审计日志）

不相关的内容包括：
- 与 Linux 无关的操作系统（Windows、macOS）的运行状态
- Linux 下的普通文件编辑、软件开发（不包括性能或资源影响）、安装软件包（除非查询资源状态）
- 纯应用层问题（如 “如何写 Python 脚本”“Vim 保存失败”）
- 与系统状态无关的 Linux 命令用法（例如 “ls 如何排序”）
- 日常闲聊、天气、新闻等

示例：

用户输入：检查一下 CPU 使用率
输出：True

用户输入：如何查看内存占用
输出：True

用户输入：我的 Ubuntu 服务器负载很高，怎么排查
输出：True

用户输入：Linux 下怎么复制文件
输出：False

用户输入：今天天气不错
输出：False

用户输入：Windows 任务管理器怎么看 CPU
输出：False


用户输入: {query}
{format_instructions}
"""
intent_recognition_prompt = PromptTemplate(
    template=intent_prompts,
    input_variables=["query"],
    partial_variables = {"format_instructions": intent_parser.get_format_instructions()},
)



status_prompts = """
你是一名专业的linux系统监控助手，能够使用工具实时获取主机的各项性能指标。请根据用户的问题，合理调用这些工具，并以清晰、结构化的方式返回监控数据。
"""
system_status_prompt = PromptTemplate(template=status_prompts)




SYSTEM_FIELD_DESCRIPTIONS = """
=== 【字段定义总览】所有指标单位、含义严格遵循以下说明 ===
1. CPU使用率 cpu_usage（单位：百分比 0.0~100.0）
    - total: 整机CPU总使用率
    - per_cpu: 每个逻辑核心的使用率列表
    - user: 用户态进程CPU占用百分比
    - system: 内核态CPU占用百分比
    - idle: CPU空闲百分比
    - iowait: 等待磁盘I/O的CPU时间百分比
    - irq/softirq: 硬中断/软中断CPU占用百分比

2. 内存使用率 mem_usage（容量单位：字节，百分比单位：0.0~100.0）
    - memory_total: 物理内存总容量
    - memory_available: 实际可用物理内存（不含缓存/缓冲区）
    - memory_used: 已使用物理内存
    - memory_percent: 物理内存使用率
    - swap_total: 交换分区总容量
    - swap_used: 已使用交换分区容量
    - swap_percent: 交换分区使用率

3. 磁盘空间使用率 disk_usage（容量单位：字节，百分比单位：0.0~100.0）
    - 外层键：磁盘挂载点（如 /、/boot/efi）
    - 内层字段：
        - total: 分区总容量
        - used: 已使用容量
        - free: 剩余可用容量
        - percent: 分区使用率
        - device: 设备文件路径
        - fstype: 文件系统类型

4. 磁盘IO disk_io（单位：字节/毫秒）
    - read_count/write_count: 读写总次数
    - read_bytes/write_bytes: 读写总字节数
    - read_time/write_time: 读写总耗时（毫秒）

5. 网络IO network_io（单位：字节/数据包个数）
    - bytes_sent/bytes_recv: 累计收发字节数
    - packets_sent/packets_recv: 累计收发数据包数
    - errin/errout: 收发错误总数
    - dropin/dropout: 收发丢包总数

6. 系统负载 system_load（单位：浮点数，代表平均活跃进程数）
    - min_1: 过去1分钟平均负载
    - min_5: 过去5分钟平均负载
    - min_15: 过去15分钟平均负载

    
7. 系统指令以及对应执行结果列表 further_check，列表中的元素字段含义:
    - command : 执行的系统指令
    - returncode: 系统指令执行返回码
    - stdout: 标准输出
    - stderr: 标准错误输出
"""
# 告警阈值规则（可根据业务需求调整）
ALERT_THRESHOLD_RULES = """
=== 【告警阈值与健康度规则】严格遵循以下标准判断 ===
1. 健康度分级
    - 健康：无任何指标触发告警，系统运行正常
    - 警告：1项非核心指标触发告警，不影响业务正常运行
    - 异常：1项核心指标触发告警，或2项及以上非核心指标告警，可能影响业务
    - 严重：2项及以上核心指标触发告警，系统已出现性能瓶颈或故障风险

2. 核心指标告警阈值（触发即至少为异常级）
    - CPU整机使用率 total > 85%，持续超过30秒
    - 物理内存使用率 memory_percent > 90%
    - 任意磁盘分区使用率 percent > 90%
    - 交换分区使用率 swap_percent > 60%（说明物理内存严重不足）
    - CPU iowait > 30%（说明磁盘IO出现严重瓶颈）
    - 1分钟系统负载 min_1 > CPU逻辑核心数（说明系统严重过载）
    - 网络收发包错误/丢包率 > 0.1%（说明网络出现异常）

3. 非核心指标告警阈值（触发为警告级）
    - CPU整机使用率 70% < total ≤ 85%
    - 物理内存使用率 75% < memory_percent ≤ 90%
    - 任意磁盘分区使用率 80% < percent ≤ 90%
    - 单CPU核心使用率持续 > 95%
    - 5分钟系统负载 min_5 > CPU逻辑核心数*0.8
    - 磁盘读写耗时持续异常升高
"""

# # 强制输出格式规范
OUTPUT_FORMAT_RULES = """
=== 【强制输出规范】必须严格输出标准JSON格式，无任何额外文本、注释、markdown ===
输出的JSON必须包含以下字段，字段名、类型完全匹配，不可新增/缺失：
{
    "health_level": "字符串，必填，只能是 健康/警告/异常/严重 四选一",
    "has_issue": "布尔值，必填，有任何告警为true，完全健康为false",
    "issue_type": "字符串或null，必填，无问题为null，有问题则为 cpu/memory/disk/network/io/unknown 多个用英文逗号分隔",
    "issue_detail": "字符串，必填，无问题填“系统运行正常，无异常指标”，有问题则详细描述异常指标、触发阈值、影响范围",
    "root_cause": "字符串或null，必填，无问题为null，有问题则定位到具体进程、行为或配置问题",
    "commands_type":"字符串或null，必填，无问题为null,有问题则为check或fix中的一个。check表示根据当前数据，无法确认具体问题，仍然需要别的指令获取系统参数判断系统问题；fix表示已经确认问题原因"，
    "fix_commands": "数组，必填，无问题为空数组[]，有问题则给出可直接执行的Linux命令，按优先级排序。commands_type值为'check', 则该参数表示linux查询指令列表(只能查询，绝对不要有任何别的操作)；如果commands_type值为'fix', 则该参数表示linux修复指令列表",
    "optimize_suggestions": "字符串，必填，无问题填“无需优化，继续保持”，有问题则给出长期优化建议"
}
"""

health_prompt = """
你是一名拥有10年以上经验的Linux系统运维专家，你的核心任务是基于给定的系统指标数据，严格按照规则完成系统健康度分析，输出精准、可落地、无歧义的结果。

--------------------------
【字段定义说明】
{field_descriptions}

【告警阈值与健康度规则】
{alert_rules}

【输出格式】
{output_rules}

【重要约束】
1. 所有分析必须完全基于当前提供的系统状态数据，禁止编造、臆测不存在的指标和问题
2. 严格遵循阈值规则，不得随意放宽或收紧告警标准
3. 必须输出纯JSON格式，禁止添加任何JSON外的文本、解释、换行、markdown格式
4. 根因分析必须定位到具体的异常点，禁止泛泛而谈
5. 修复命令必须是可直接在Linux系统执行的有效命令，禁止无效、危险的操作
6、 如果发现问题，不要重复查询已知参数，尽快给出修复指令。

--------------------------

【当前系统状态数据】
{system_status_json}
进一步诊断获取的数据
{further_check_status_json}

{format_instructions}
"""
system_health_prompt = PromptTemplate(
    template=health_prompt,
    input_variables=["system_status_json"],
    partial_variables={
        "format_instructions": system_report_parser.get_format_instructions(),
        "field_descriptions":SYSTEM_FIELD_DESCRIPTIONS,
        "alert_rules":ALERT_THRESHOLD_RULES,
        "output_rules":OUTPUT_FORMAT_RULES
    },

)




command_executor_prompt = PromptTemplate(template="""
你是一名Linux指令执行者，你的核心任务是基于给定的linux指令列表，将linux指令列表传递给工具执行Linux命令。
# 约束
1、将整个指令列表传递给工具，不要逐一传递
""")



chat_prompt = ChatPromptTemplate.from_messages([
    ("system","你是一个有用的聊天助手，能够回答用户问题"),
    MessagesPlaceholder(variable_name="messages"),]
)


fix_result_template = """
你是一个linux系统状态监测助手，能够根据输入的信息，来总结并返回当前Linux操作系统的状态。
输入的JSON包含以下字段
{{
    "has_issue": "布尔值，必填，有任何告警为true，完全健康为false",
    "issue_type": "字符串或null，必填，无问题为null，有问题则为 cpu/memory/disk/network/io/unknown 多个用英文逗号分隔",
    "issue_detail": "字符串，必填，无问题填“系统运行正常，无异常指标”，有问题则详细描述异常指标、触发阈值、影响范围",
    "root_cause": "字符串或null，必填，无问题为null，有问题则分析异常根因，定位到具体进程、行为或配置问题",
    "commands_type":"字符串或null，必填，无问题为null,有问题则为check或fix中的一个。check表示根据当前数据，无法确认具体问题，仍然需要别的指令获取系统参数判断系统问题；fix表示已经确认问题原因"，
    "fix_commands": "数组，必填，无问题为空数组[]，有问题则给出可直接执行的Linux命令，按优先级排序。commands_type值为'check', 则该参数表示linux查询指令列表(只能查询，绝对不要有任何别的操作)；如果commands_type值为'fix', 则该参数表示linux修复指令列表",
    "optimize_suggestions": "字符串，必填，无问题填“无需优化，继续保持”，有问题则给出长期优化建议",
    "further_check": 系统指令以及对应执行结果列表，每一个元素是一个字典元素字段含义:
        - command : 执行的系统指令
        - returncode: 系统指令执行返回码
        - stdout: 标准输出
        - stderr: 标准错误输出,
    "further_check_count":"系统排查次数，如果该值大于6，则提示用户系统未定位到根本问题",
    "fix_result": 列表或null，表示执行的修复指令的列表，每一个列表元素包含以下字段：
        - command : 执行的系统指令
        - is_sensitive: 是否是敏感指令
        - confirmed: 是否执行
        - success: 是否执行成功
        - output: 输出信息
        
}}
你应该能够根据这些字段,使用简单易懂的语言，组织并描述当前操作系统的健康状态。如果系统状态异常，你应该能够给出专业排查及优化建议
用户输入: {system_status}
"""

result_prompt = PromptTemplate(
    template=fix_result_template,
    input_variables=["system_status"],
)