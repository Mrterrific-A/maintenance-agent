import json

from langchain.tools import tool
import psutil
import time
import os
import re
from utils.utils import bytes_to_M
from utils.states import SystemState
from typing_extensions import List
import subprocess
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field
class CommandCheck(BaseModel):
    command_list: List[str] = Field(
        description="linux指令列表，每一个列表元素是linux指令字符串"
    )


@tool
def get_memory_usage():
    """
    获取内存利用率
    Returns:
    dict: 包含以下 7 个字段的字典（所有数值单位均为字节，百分比为浮点数）：
        - memory_total (int): 物理内存总容量（字节）
        - memory_available (int): 实际可用的物理内存（字节，不包括缓存和缓冲区）
        - memory_used (int): 已使用的物理内存（字节，total - available - 系统保留）
        - memory_percent (float): 物理内存使用百分比（0.0~100.0）
        - swap_total (int): 交换分区总容量（字节）
        - swap_used (int): 已使用的交换分区容量（字节）
        - swap_percent (float): 交换分区使用百分比（0.0~100.0）

    示例返回值：
        {
            "memory_total": 17179869184,
            "memory_available": 8589934592,
            "memory_used": 8589934592,
            "memory_percent": 50.0,
            "swap_total": 4294967296,
            "swap_used": 2147483648,
            "swap_percent": 50.0
        }
    """
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    data = {
        "memory_total": memory.total,
        "memory_available": memory.available,
        "memory_used": memory.used,
        "memory_percent": memory.percent,
        "swap_total": swap.total,
        "swap_used": swap.used,
        "swap_percent": swap.percent
    }
    writer = get_stream_writer()
    writer({"内存情况:": json.dumps(data)})
    return data


@tool
def get_disk_usage():
    """
    获取磁盘空间利用率
    Returns:
        dict:
            以挂载点为键（str），以磁盘信息字典为值的映射。
            每个磁盘信息字典包含以下字段：
                - total (int): 分区总容量（字节）
                - used (int): 已使用容量（字节）
                - free (int): 剩余可用容量（字节）
                - percent (float): 使用百分比（0.0~100.0）
                - device (str): 设备文件路径，例如 "/dev/sda1"
                - fstype (str): 文件系统类型，例如 "ext4", "ntfs"

        示例返回值：
            {
                "/": {
                    "total": 500107862016,
                    "used": 120489570304,
                    "free": 379240067072,
                    "percent": 24.1,
                    "device": "/dev/sda2",
                    "fstype": "ext4"
                },
                "/boot/efi": {
                    "total": 536870912,
                    "used": 32768000,
                    "free": 504102912,
                    "percent": 6.1,
                    "device": "/dev/sda1",
                    "fstype": "vfat"
                }
            }

    """
    disk_usage = {}
    partitions = psutil.disk_partitions()
    for partition in partitions:
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_usage[partition.mountpoint] = {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
                "device": partition.device,
                "fstype": partition.fstype
            }
        except (PermissionError, OSError):
            # 忽略无法访问的文件系统
            continue
    writer = get_stream_writer()
    writer({"磁盘利用率情况:": json.dumps(disk_usage)})
    return disk_usage


def get_disk_io_from_proc():
    """从 /proc/diskstats 手动解析磁盘I/O信息"""
    try:
        with open('/proc/diskstats', 'r') as f:
            lines = f.readlines()

        total_reads = 0
        total_writes = 0
        total_read_bytes = 0
        total_write_bytes = 0

        for line in lines:
            # 跳过空行和注释
            if not line.strip() or line.startswith('#'):
                continue

            parts = line.split()
            # /proc/diskstats 格式:
            # major minor name reads reads_merged sectors_read ms_read writes writes_merged sectors_written ms_writes
            if len(parts) >= 11:
                device_name = parts[2]
                # 跳过分区 (sda1, sdb2 等) 和虚拟设备
                if re.search(r'\d+$', device_name) or device_name.startswith(('loop', 'ram', 'fd')):
                    continue

                reads = int(parts[3])
                sectors_read = int(parts[5])
                writes = int(parts[7])
                sectors_written = int(parts[9])

                total_reads += reads
                total_writes += writes
                total_read_bytes += sectors_read * 512  # 每个扇区512字节
                total_write_bytes += sectors_written * 512
        data={
            "read_count": total_reads,
            "write_count": total_writes,
            "read_bytes": total_read_bytes,
            "write_bytes": total_write_bytes,
            "read_time": 0,  # 这些值在 /proc/diskstats 中不容易聚合
            "write_time": 0
        }

        return data
    except (IOError, OSError, IndexError, ValueError):
        # 如果无法读取或解析 /proc/diskstats，返回默认值
        return {
            "read_count": 0,
            "write_count": 0,
            "read_bytes": 0,
            "write_bytes": 0,
            "read_time": 0,
            "write_time": 0
        }


@tool
def get_disk_io():
    """获取磁盘I/O统计信息 - 修复版本

     Returns:
        dict: 包含以下字段的字典：
            - read_count (int): 读取总次数
            - write_count (int): 写入总次数
            - read_bytes (int): 读取总字节数
            - write_bytes (int): 写入总字节数
            - read_time (int): 读取总耗时（毫秒）
            - write_time (int): 写入总耗时（毫秒）

        示例返回值：
            {
                "read_count": 12345,
                "write_count": 6789,
                "read_bytes": 104857600,
                "write_bytes": 51200000,
                "read_time": 1234,
                "write_time": 5678
            }

    """
    try:
        disk_io = psutil.disk_io_counters()
        if disk_io is None:
            return get_disk_io_from_proc()
        data={
            "read_count": disk_io.read_count,
            "write_count": disk_io.write_count,
            "read_bytes": disk_io.read_bytes,
            "write_bytes": disk_io.write_bytes,
            "read_time": disk_io.read_time,
            "write_time": disk_io.write_time
        }
        writer = get_stream_writer()
        writer({"磁盘IO情况:": json.dumps(data)})
        return data
    except (ValueError, AttributeError):
        # 如果 psutil 无法解析 /proc/diskstats，使用备选方案
        return get_disk_io_from_proc()


@tool
def get_network_io():
    """
    获取网络I/O统计信息
    使用 psutil 读取所有网络接口的累计收发字节数、数据包数、错误数和丢包数。
    如果无法获取统计信息（如权限不足或 psutil 不支持），则返回全零的默认值。

    Returns:
        dict: 包含以下 8 个字段的字典（所有数值均为整数，单位为字节或数据包个数）：
            - bytes_sent (int): 累计发送的字节数
            - bytes_recv (int): 累计接收的字节数
            - packets_sent (int): 累计发送的数据包数量
            - packets_recv (int): 累计接收的数据包数量
            - errin (int): 接收时发生的错误总数
            - errout (int): 发送时发生的错误总数
            - dropin (int): 接收时丢弃的数据包总数
            - dropout (int): 发送时丢弃的数据包总数

        示例返回值：
            {
                "bytes_sent": 1234567890,
                "bytes_recv": 9876543210,
                "packets_sent": 1234567,
                "packets_recv": 9876543,
                "errin": 0,
                "errout": 0,
                "dropin": 2,
                "dropout": 0
            }

        当统计信息不可用时的返回值：
            {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_sent": 0,
                "packets_recv": 0,
                "errin": 0,
                "errout": 0,
                "dropin": 0,
                "dropout": 0
            }
    """
    try:
        net_io = psutil.net_io_counters()
        data={
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "errin": net_io.errin,
            "errout": net_io.errout,
            "dropin": net_io.dropin,
            "dropout": net_io.dropout
        }
        writer = get_stream_writer()
        writer({"网络IO情况:": json.dumps(data)})
        return data
    except (ValueError, AttributeError):
        # 如果网络统计信息不可用，返回默认值
        return {
            "bytes_sent": 0,
            "bytes_recv": 0,
            "packets_sent": 0,
            "packets_recv": 0,
            "errin": 0,
            "errout": 0,
            "dropin": 0,
            "dropout": 0
        }


@tool
def get_system_load():
    """
    获取系统负载
    分别返回过去 1 分钟、5 分钟和 15 分钟的系统平均负载值。
    负载值表示处于可运行或不可中断状态的进程平均数量（包括正在运行和等待 I/O 的进程）。
    如果操作系统不支持获取负载（如 Windows 上的 `os.getloadavg()` 可能不可用），则返回全 0 的默认值。

    Returns:
        dict: 包含以下 3 个字段的字典（所有值均为浮点数）：
            - min_1 (float): 过去 1 分钟的系统平均负载
            - min_5 (float): 过去 5 分钟的系统平均负载
            - min_15 (float): 过去 15 分钟的系统平均负载

        说明：
            - 在 Linux/Unix 系统中，负载值通常以 CPU 核心数为参考，例如值为 1.0 表示单核满载。
            - 不同操作系统或环境下的计算方式可能略有差异。

        示例返回值（正常情况）：
            {
                "min_1": 2.35,
                "min_5": 1.85,
                "min_15": 1.42
            }

        当无法获取负载时的返回值（异常情况）：
            {
                "min_1": 0.0,
                "min_5": 0.0,
                "min_15": 0.0
            }
    """
    try:
        load_avg = os.getloadavg()
        data={
            "min_1": load_avg[0],
            "min_5": load_avg[1],
            "min_15": load_avg[2]
        }
        writer = get_stream_writer()
        writer({"系统负载情况:": json.dumps(data)})
        return data
    except OSError:
        # 如果无法获取负载平均值，返回默认值
        return {
            "min_1": 0,
            "min_5": 0,
            "min_15": 0
        }


@tool
def get_cpu_usage():
    """
    获取CPU利用率
    分别采集总体 CPU 使用率、每个逻辑核心的使用率，以及 CPU 时间在各状态下的百分比分布。
    采集时间间隔为 0.1 秒，以获取瞬时或短时平均负载。

    Returns:
        dict: 包含以下字段的字典（所有百分比值均为浮点数，范围 0.0~100.0）：
            - total (float): 总体 CPU 使用率（所有核心平均）
            - per_cpu (List[float]): 每个逻辑核心的使用率列表，顺序与核心编号对应
            - user (float): 用户态进程占用 CPU 的百分比
            - system (float): 内核态（系统）占用 CPU 的百分比
            - idle (float): CPU 空闲百分比
            - iowait (float): 等待 I/O 操作完成的 CPU 时间百分比（部分系统可能为 0）
            - irq (float): 处理硬件中断的 CPU 百分比
            - softirq (float): 处理软件中断的 CPU 百分比

        示例返回值（8 核系统）：
            {
                "total": 23.5,
                "per_cpu": [15.2, 18.7, 22.1, 30.4, 17.8, 19.3, 25.6, 28.9],
                "user": 18.2,
                "system": 5.3,
                "idle": 76.5,
                "iowait": 0.0,
                "irq": 0.0,
                "softirq": 0.0
            }

        当无法获取 CPU 信息时的返回值（异常情况）：
            {
                "total": 0.0,
                "per_cpu": [0.0],
                "user": 0.0,
                "system": 0.0,
                "idle": 100.0,
                "iowait": 0.0,
                "irq": 0.0,
                "softirq": 0.0
            }
    """
    try:
        # 获取每个核心的利用率
        per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
        # 获取总体利用率
        total_cpu = psutil.cpu_percent(interval=0.1)
        # 获取CPU统计信息
        cpu_times = psutil.cpu_times_percent(interval=0.1)

        data ={
            "total": total_cpu,
            "per_cpu": per_cpu,
            "user": getattr(cpu_times, 'user', 0),
            "system": getattr(cpu_times, 'system', 0),
            "idle": getattr(cpu_times, 'idle', 0),
            "iowait": getattr(cpu_times, 'iowait', 0),
            "irq": getattr(cpu_times, 'irq', 0),
            "softirq": getattr(cpu_times, 'softirq', 0)
        }
        writer = get_stream_writer()
        writer({"cpu利用率情况:": json.dumps(data)})
        return data
    except (AttributeError, OSError):
        # 如果无法获取CPU信息，返回默认值
        return {
            "total": 0,
            "per_cpu": [0],
            "user": 0,
            "system": 0,
            "idle": 100,
            "iowait": 0,
            "irq": 0,
            "softirq": 0
        }

# @tool(args_schema=CommandCheck)
@tool
def run_command(command_list):
    """
    执行系统命令并返回结果。

    :param command_list: linux命令字符串列表（如 "ls -l"）
    :type command_list: list
    :return: 包含返回码、stdout、stderr 的字典列表，比如[{"command":"ls -l", "returncode":0,"stdout":"","stderr":""}]
    """
    # print(">>>>>>>>>>>>>>>>>>>")
    # print(command_list)
    res_list=[]
    writer = get_stream_writer()
    for command in command_list:
        try:
            writer({"执行指令: ": command})
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=90)
            data = {
                "command": command,
                "returncode": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
            res_list.append(data)
            writer({"执行结果: ": json.dumps(data)})

        except subprocess.TimeoutExpired:
            res_list.append({
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": "Command timeout"
            })
    return res_list
# @tool
# def monitor_system(interval=1):
#     """
#     监控系统各项指标
#     通过两次采样（间隔 interval 秒）计算磁盘和网络的传输速率（吞吐量）。
#     注意：磁盘读写吞吐量基于采样间隔内的绝对变化量（字节），未除以时间间隔，因此实际输出的是间隔内的总传输量（字节）；
#     网络吞吐量则已除以时间间隔，得到字节/秒速率，且总网络吞吐量会转换为 MB/秒。
#
#     要求系统存在 '/runtime' 和 '/var' 等典型 Linux 分区，否则 `psutil.disk_usage` 可能抛出异常。
#
#     Args:
#         interval (float): 采样间隔时间，单位为秒，默认为 1。函数会先记录初始计数器，等待 interval 秒后再次采样。
#
#     Returns:
#         dict: 包含以下顶级字段的字典，所有数值均以字符串形式返回（方便直接输出）：
#             - memory (str): 内存使用率，取值范围 0~1 之间的小数（例如 "0.4532" 表示 45.32%）
#             - cpu (str): CPU 总体使用率，取值范围 0~1 之间的小数（例如 "0.2350" 表示 23.50%）
#             - disk_usage (dict): 磁盘分区使用率，包含三个子字段：
#                 - system_partition (str): 根分区 `'/'` 的使用率（小数，0~1）
#                 - log_partition (str): `/runtime` 分区的使用率（小数，0~1）
#                 - data_partition (str): `/var` 分区的使用率（小数，0~1）
#             - system_load (dict): 系统平均负载，包含三个子字段：
#                 - 1min (str): 过去 1 分钟的平均负载（保留 1 位小数）
#                 - 5min (str): 过去 5 分钟的平均负载（保留 1 位小数）
#                 - 15min (str): 过去 15 分钟的平均负载（保留 1 位小数）
#             - disk_io (dict): 磁盘 I/O 统计信息，包含：
#                 - disk_throughput (str): 采样间隔内磁盘读取的总字节数（原始差值，未除以时间）
#                 - disk_write_throughput (str): 采样间隔内磁盘写入的总字节数，并转换为 MB（通过 `self.bytes_to_M()`）
#             - net_io (dict): 网络 I/O 统计信息，包含：
#                 - net_sent_throughput (str): 采样间隔内的网络发送速率（字节/秒，原始值）
#                 - net_recv_throughput (str): 采样间隔内的网络接收速率（字节/秒，原始值）
#                 - net_throughput (str): 总网络吞吐量（发送+接收），并转换为 MB/秒（通过 `self.bytes_to_M()`）
#
#         示例返回值：
#             {
#                 "memory": "0.4523",
#                 "cpu": "0.2350",
#                 "disk_usage": {
#                     "system_partition": "0.4523",
#                     "log_partition": "0.1234",
#                     "data_partition": "0.6789"
#                 },
#                 "system_load": {
#                     "1min": "1.2",
#                     "5min": "1.0",
#                     "15min": "0.8"
#                 },
#                 "disk_io": {
#                     "disk_throughput": "1048576",
#                     "disk_write_throughput": "2.50"
#                 },
#                 "net_io": {
#                     "net_sent_throughput": "102400",
#                     "net_recv_throughput": "204800",
#                     "net_throughput": "0.29"
#                 }
#             }
#
#     Raises:
#         FileNotFoundError: 当访问不存在的分区路径（如 '/runtime' 或 '/var'）时，`psutil.disk_usage` 可能抛出异常。
#         PermissionError: 当没有权限访问某些分区统计信息时可能抛出。
#     """
#
#     # 获取初始磁盘和网络I/O计数
#     prev_disk_io = get_disk_io()
#     prev_net_io = get_network_io()
#     prev_time = time.time()
#
#     time.sleep(interval)
#
#     # 获取当前时间
#     current_time = time.time()
#     elapsed = current_time - prev_time
#
#     # 获取各项指标
#     memory = get_memory_usage()
#     disk_usage = get_disk_usage()
#     current_disk_io = get_disk_io()
#     current_net_io = get_network_io()
#     load = get_system_load()
#     cpu = get_cpu_usage()
#
#     # 计算磁盘吞吐量（字节/秒）
#     disk_read_throughput = (current_disk_io["read_bytes"] - prev_disk_io["read_bytes"])
#     disk_write_throughput = (current_disk_io["write_bytes"] - prev_disk_io["write_bytes"])
#
#     # 计算网络吞吐量（字节/秒）
#     net_sent_throughput = (current_net_io["bytes_sent"] - prev_net_io["bytes_sent"]) / elapsed
#     net_recv_throughput = (current_net_io["bytes_recv"] - prev_net_io["bytes_recv"]) / elapsed
#     net_throughput = net_sent_throughput + net_recv_throughput
#     partitions = psutil.disk_partitions()
#     # disk_usage = psutil.disk_usage('/').percent
#     # try:
#         # 总磁盘利用率
#         # used_disk = sum([psutil.disk_usage(partition.mountpoint).used for partition in partitions])
#         # total_disk = sum([psutil.disk_usage(partition.mountpoint).total for partition in partitions])
#         # disk_usage = round((used_disk / total_disk) * 100, 2)
#
#     system_partition= psutil.disk_usage('/').percent
#     log_partition = psutil.disk_usage('/runtime').percent
#     data_partition = psutil.disk_usage('/var').percent
#
#     # except:
#     #     disk_usage = psutil.disk_usage('/').percent
#
#     data = {
#         "memory": f"{memory['memory_percent']/100:.4f}",
#         "cpu":f"{cpu['total']/100:.4f}",
#         "disk_usage": {
#             "system_partition": f"{system_partition/100:.4f}",
#             "log_partition": f"{log_partition / 100:.4f}",
#             "data_partition": f"{data_partition / 100:.4f}",
#         },
#         "system_load":{
#             "1min": f"{load['1min']:.1f}",
#             "5min": f"{load['5min']:.1f}",
#             "15min": f"{load['15min']:.1f}"
#         },
#         "disk_io":{
#             "disk_throughput": f"{disk_read_throughput}",
#             "disk_write_throughput": f"{bytes_to_M(disk_write_throughput)}",
#         },
#         "net_io":{
#             "net_sent_throughput": f"{net_sent_throughput}",
#             "net_recv_throughput": f"{net_recv_throughput}",
#             "net_throughput": f"{bytes_to_M(net_throughput)}"
#         }
#     }
#     return data


tools = [get_memory_usage,get_disk_usage, get_disk_io, get_network_io, get_system_load,get_cpu_usage, run_command]
tools_by_name = {tool.name: tool for tool in tools}