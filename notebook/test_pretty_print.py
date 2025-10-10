"""
测试 pretty print 功能
"""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box

# 测试各种输出格式
console = Console()

# 测试 1: Panel 输出
print("\n=== 测试 1: Panel 输出 ===")
content = Text()
content.append("📋 当前任务: ", style="bold cyan")
content.append("获取数据\n", style="white")
content.append("📊 数据状态: ", style="bold cyan")
content.append("OHLCV=✓, 指标=✗, 信号=✗\n", style="white")

panel = Panel(
    content,
    title="🔹 节点: data_fetch (步骤 1)",
    border_style="blue",
    box=box.ROUNDED,
    padding=(0, 1)
)
console.print(panel)

# 测试 2: Table 输出
print("\n=== 测试 2: Table 输出 ===")
table = Table(title="📈 执行摘要", show_header=False, box=box.DOUBLE_EDGE)
table.add_column("项目", style="bold cyan", width=20)
table.add_column("状态", style="white")

table.add_row("OHLCV数据", "✅ 就绪")
table.add_row("指标数据", "❌ 未就绪")
table.add_row("交易信号", "❌ 未就绪")
table.add_row("执行步骤数", "5")
table.add_row("错误次数", "0")
table.add_row("重试次数", "0")

console.print(table)

# 测试 3: 标题和分隔符
print("\n=== 测试 3: 标题和分隔符 ===")
console.print()
console.print("="*60, style="bold cyan")
console.print("🚀 开始流式执行信号生成子图", style="bold cyan", justify="center")
console.print("="*60, style="bold cyan")
console.print()

console.print("="*60, style="bold green")
console.print("✅ 子图执行完成", style="bold green", justify="center")
console.print("="*60, style="bold green")

print("\n✅ 所有测试完成！Rich 库工作正常。")
