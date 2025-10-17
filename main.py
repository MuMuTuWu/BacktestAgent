"""
项目入口：演示完整 LangGraph 流程（信号生成 → 回测 → PNL 绘制）。

支持 human-in-the-loop：
- 如果执行过程中需要用户澄清（如 clarify_node），图会暂停
- 使用 Command(resume={"data": response}) 恢复执行
"""
from __future__ import annotations

import dotenv
from langgraph.types import Command

from src.config import configurable
from src.graph import (
    build_initial_state,
    build_run_config,
    create_main_graph,
)
from src.state import GLOBAL_DATA_STATE

dotenv.load_dotenv()


def main(query: str, thread_id: str = "main-session") -> None:
    """
    执行完整流程
    
    Args:
        query: 用户查询
        thread_id: 会话ID，用于状态持久化
    """
    print("\n" + "=" * 80)
    print("🎯 开始执行完整流程：信号生成 → 回测 → PNL绘制")
    print("=" * 80 + "\n")
    print(f"日志目录: {configurable['task_dir']}")
    print(f"会话ID: {thread_id}\n")

    # 创建带 checkpointer 的主图
    graph = create_main_graph()  # 默认使用 MemorySaver
    initial_state = build_initial_state(query)
    run_config = build_run_config(thread_id=thread_id)

    # 执行完整流程
    final_state = graph.invoke(initial_state, config=run_config)
    # 执行完成
    _print_final_results(final_state)

def _print_final_results(final_state: dict) -> None:
    """打印最终结果"""
    print("\n" + "=" * 80)
    print("✅ 完整流程执行完成")
    print("=" * 80 + "\n")

    print(f"信号生成: {'✅ 成功' if final_state.get('signal_ready') else '❌ 失败'}")
    print(f"回测完成: {'✅ 成功' if final_state.get('backtest_ready') else '❌ 失败'}")
    if final_state.get("errors"):
        print(f"异常信息: {len(final_state['errors'])} 条，详情见日志目录。")

    snapshot = GLOBAL_DATA_STATE.snapshot()
    print("\nGLOBAL_DATA_STATE:")
    print(f"  - OHLCV字段: {list(snapshot.get('ohlcv', {}).keys())}")
    print(f"  - 信号字段: {list(snapshot.get('signal', {}).keys())}")
    print(f"  - 回测结果字段: {list(snapshot.get('backtest_results', {}).keys())}")


if __name__ == "__main__":
    query = "请获取000001.SZ从20240901到20250901的数据，然后生成5日和20日均线交叉策略信号，并执行回测"
    main(query)
