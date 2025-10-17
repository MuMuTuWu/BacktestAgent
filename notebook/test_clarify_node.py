"""
测试 clarify_node 的 human-in-the-loop 功能

演示如何：
1. 触发 clarify_node 并暂停执行
2. 检查图的状态
3. 使用 Command 恢复执行并提供用户响应
"""
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from src.subgraphs.signal.graph import create_signal_subgraph


def test_clarify_with_interrupt():
    """测试 clarify_node 的中断和恢复流程"""
    
    # 创建带 checkpointer 的子图
    checkpointer = MemorySaver()
    signal_graph = create_signal_subgraph()
    signal_graph_compiled = signal_graph.compile(checkpointer=checkpointer)
    
    # 配置线程ID以支持持久化
    config = {"configurable": {"thread_id": "test-clarify-1"}}
    
    # 初始状态：模拟需要澄清的情况
    initial_state = {
        "messages": [
            {"role": "user", "content": "帮我生成一个交易信号"}
        ],
        "current_task": "clarify",
        "data_ready": False,
        "indicators_ready": False,
        "signal_ready": False,
        "user_intent": {
            "type": "signal_generation",
            "params": {
                "strategy_desc": "均线策略"
            },
            "needs_clarification": True
        },
        "clarification_needed": "缺少股票代码和时间范围",
        "clarification_count": 0,
        "execution_history": [],
        "error_messages": [],
        "max_retries": 3,
        "retry_count": 0,
    }
    
    print("=" * 80)
    print("步骤 1: 启动图执行，触发 clarify_node")
    print("=" * 80)
    
    # 第一次执行：会在 clarify_node 处中断
    try:
        events = []
        for event in signal_graph_compiled.stream(initial_state, config, stream_mode="values"):
            events.append(event)
            print(f"\n收到事件: {event.get('current_task', 'unknown')}")
    except Exception as e:
        print(f"执行被中断（这是预期的）: {e}")
    
    print("\n" + "=" * 80)
    print("步骤 2: 检查图的状态")
    print("=" * 80)
    
    # 获取当前状态
    snapshot = signal_graph_compiled.get_state(config)
    print(f"\n当前节点: {snapshot.next}")
    print(f"澄清次数: {snapshot.values.get('clarification_count', 0)}")
    
    # 检查中断值（包含澄清问题）
    if hasattr(snapshot, 'tasks') and snapshot.tasks:
        for task in snapshot.tasks:
            if hasattr(task, 'interrupts') and task.interrupts:
                for interrupt_info in task.interrupts:
                    print(f"\n中断信息:")
                    print(f"  - 澄清原因: {interrupt_info.value.get('clarification_reason')}")
                    print(f"  - 澄清问题: {interrupt_info.value.get('query')[:100]}...")
    
    print("\n" + "=" * 80)
    print("步骤 3: 使用 Command 恢复执行并提供用户响应")
    print("=" * 80)
    
    # 用户提供的响应
    user_response = "我想分析 000001.SZ，时间范围是 20240101 到 20241231"
    
    # 使用 Command 恢复执行
    # 注意：必须使用 {"data": user_response} 格式
    resume_command = Command(resume={"data": user_response})
    
    print(f"\n用户响应: {user_response}")
    print("恢复执行...")
    
    # 继续执行
    try:
        for event in signal_graph_compiled.stream(resume_command, config, stream_mode="values"):
            print(f"\n收到事件: {event.get('current_task', 'unknown')}")
            if event.get('messages'):
                last_msg = event['messages'][-1]
                if hasattr(last_msg, 'content'):
                    print(f"消息内容: {last_msg.content[:100]}...")
    except Exception as e:
        print(f"执行完成或再次中断: {e}")
    
    print("\n" + "=" * 80)
    print("步骤 4: 再次检查图的状态")
    print("=" * 80)
    
    final_snapshot = signal_graph_compiled.get_state(config)
    print(f"\n当前节点: {final_snapshot.next}")
    print(f"澄清次数: {final_snapshot.values.get('clarification_count', 0)}")
    print(f"消息数量: {len(final_snapshot.values.get('messages', []))}")
    
    print("\n测试完成！")


def test_multiple_clarifications():
    """测试多次澄清的场景"""
    
    print("\n" + "=" * 80)
    print("测试场景：多次澄清")
    print("=" * 80)
    
    checkpointer = MemorySaver()
    signal_graph = create_signal_subgraph()
    signal_graph_compiled = signal_graph.compile(checkpointer=checkpointer)
    
    config = {"configurable": {"thread_id": "test-clarify-multi"}}
    
    # 模拟需要多次澄清的情况
    initial_state = {
        "messages": [
            {"role": "user", "content": "帮我生成信号"}
        ],
        "current_task": "clarify",
        "data_ready": False,
        "indicators_ready": False,
        "signal_ready": False,
        "user_intent": {
            "type": "signal_generation",
            "params": {},
            "needs_clarification": True
        },
        "clarification_needed": "缺少所有必要信息",
        "clarification_count": 0,
        "execution_history": ["尝试解析用户意图"],
        "error_messages": ["缺少股票代码", "缺少时间范围", "缺少策略描述"],
        "max_retries": 3,
        "retry_count": 1,
    }
    
    # 第一次澄清
    print("\n第一次澄清...")
    try:
        for event in signal_graph_compiled.stream(initial_state, config, stream_mode="values"):
            pass
    except:
        pass
    
    snapshot = signal_graph_compiled.get_state(config)
    print(f"澄清次数: {snapshot.values.get('clarification_count', 0)}")
    
    # 提供部分信息
    resume_cmd = Command(resume={"data": "股票代码是 000001.SZ"})
    try:
        for event in signal_graph_compiled.stream(resume_cmd, config, stream_mode="values"):
            pass
    except:
        pass
    
    print("\n第一次澄清完成")
    final_snapshot = signal_graph_compiled.get_state(config)
    print(f"最终澄清次数: {final_snapshot.values.get('clarification_count', 0)}")
    print(f"执行历史: {final_snapshot.values.get('execution_history', [])}")


if __name__ == "__main__":
    print("测试 clarify_node 的 human-in-the-loop 功能\n")
    
    try:
        test_clarify_with_interrupt()
    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test_multiple_clarifications()
    except Exception as e:
        print(f"\n多次澄清测试出错: {e}")
        import traceback
        traceback.print_exc()

