from pathlib import Path
from datetime import datetime
import re

# 获取当天日期字符串，格式为 yyyy-mm-dd
today_str = datetime.now().strftime("%Y-%m-%d")

# 构建输出目录路径
ROOT_DIR = Path(__file__).parent.parent
output_dir = ROOT_DIR / "workspace" / today_str
# 创建目录（如果还未创建）
output_dir.mkdir(parents=True, exist_ok=True)


def get_task_directory(base_dir):
    """
    获取可用的task目录
    如果最大编号的task文件夹为空，则直接使用；否则创建新的task文件夹
    """
    task_pattern = re.compile(r'^task-(\d+)$')
    max_number = 0
    max_task_dir = None

    # 遍历目录下的所有项目
    if base_dir.exists():
        for item in base_dir.iterdir():
            if item.is_dir():
                match = task_pattern.match(item.name)
                if match:
                    number = int(match.group(1))
                    if number > max_number:
                        max_number = number
                        max_task_dir = item

    # 如果存在task文件夹且最大编号的文件夹为空，则使用它
    if max_task_dir and max_task_dir.exists():
        # 检查文件夹是否为空（忽略隐藏文件）
        contents = [item for item in max_task_dir.iterdir() if not item.name.startswith('.')]
        if not contents:
            return max_task_dir

    # 否则创建新的task文件夹
    new_task_number = max_number + 1
    new_task_dir = base_dir / f"task-{new_task_number}"
    new_task_dir.mkdir(parents=True, exist_ok=True)
    return new_task_dir


# 获取可用的task目录
task_dir = get_task_directory(output_dir)

configurable = {
    "task_dir": task_dir,
    "model_name": "openai:gpt-5-mini",
    "light_model_name": "openai:gpt-5-nano",
}
