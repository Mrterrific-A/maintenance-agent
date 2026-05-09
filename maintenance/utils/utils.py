import subprocess

def supervisor_check(process):
    command = ["supervisorctl status %s | awk '{print $2}'" % process]

    res = subprocess.run(command,shell=True, check=False, capture_output=True, text=True)
    exit_code = res.returncode
    # 获取标准输出内容
    stdout_content = str(res.stdout).strip('\n').strip(" ")
    # 获取标准错误内容
    stderr_content = str(res.stderr).strip(" ").strip("\n")
    status = str(stdout_content[1]).strip(" ")
    if exit_code != 0:
        return False
    if stdout_content == "RUNNING":
        return True
    else:
        return False


def system_check(process):
    command = ["systemctl","is-active", "%s" % process]
    res = subprocess.run(command, capture_output=True, text=True)
    exit_code = res.returncode
    # 获取标准输出内容
    stdout_content = str(res.stdout).strip(" ").strip("\n")
    # 获取标准错误内容
    stderr_content = str(res.stderr).strip(" ").strip("\n")
    if exit_code != 0:
        return False
    if str(stdout_content).strip(" ").strip("\n") == "active":
        return True
    else:
        return False


def get_disk(path):
    command = ["du", "-sm", "%s" % path]

    res = subprocess.run(command, capture_output=True, text=True)
    exit_code = res.returncode
    # 获取标准输出内容
    stdout_content = str(res.stdout).strip('\n').split("\t")
    # 获取标准错误内容
    stderr_content = str(res.stderr).strip(" ").strip("\n")
    if exit_code != 0:
        return False
    disk_usage = str(stdout_content[0]).strip(" ")

    return disk_usage

def bytes_to_human(n):
    """将字节数转换为易读格式"""
    if n == 0:
        return "0B"

    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i + 1) * 10

    for s in reversed(symbols):
        if n >= prefix[s]:
            value = float(n) / prefix[s]
            return '%.1f%s' % (value, s)
    return "%sB" % n

def bytes_to_M(n):
    """将字节数转换为易读格式"""
    if n == 0:
        return "0"


    return f"{float(n)/1024/1024:.3f}"