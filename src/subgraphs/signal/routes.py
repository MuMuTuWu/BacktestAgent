"""
信号生成子图的路由函数
"""
from langgraph.graph import END
from .state import SignalSubgraphState


def route_from_reflection(state: SignalSubgraphState) -> str:
    """从反思节点出发的路由决策
    
    根据reflection节点输出的next_action字段进行路由
    """
    
    # 获取reflection节点决定的下一步行动
    next_action = state.get('next_action', 'end')
    
    # 映射next_action到路由目标
    route_map = {
        'data_fetch': 'data_fetch',
        'signal_generate': 'signal_generate',
        'validate': 'validate',
        'end': END,
    }
    
    return route_map.get(next_action, END)


def route_after_data_fetch(state: SignalSubgraphState) -> str:
    """数据获取后的路由"""
    
    # 检查是否有错误
    if state.get('error_messages'):
        retry_count = state.get('retry_count', 0)
        max_retries = state.get('max_retries', 3)
        
        if retry_count < max_retries:
            # 重新评估
            return 'reflection'
        else:
            # 多次失败，终止执行
            return END
    
    # 验证数据质量
    return 'validate'


def route_after_signal_gen(state: SignalSubgraphState) -> str:
    """信号生成后的路由"""
    
    # 检查是否有错误
    if state.get('error_messages'):
        # 重新评估策略
        return 'reflection'
    
    # 验证信号质量
    return 'validate'


def route_after_validation(state: SignalSubgraphState) -> str:
    """验证后的路由"""
    
    # 如果验证发现问题且未超过重试次数
    if state.get('error_messages'):
        retry_count = state.get('retry_count', 0)
        max_retries = state.get('max_retries', 3)
        
        if retry_count < max_retries:
            return 'reflection'  # 继续改进
        else:
            # 无法自动修复，终止执行
            return END
    
    # 验证通过，检查任务完成状态
    next_action = state.get('next_action', 'end')
    
    if next_action == 'data_fetch' and state.get('data_ready'):
        return END  # 数据获取任务完成
    
    if next_action == 'signal_generate' and state.get('signal_ready'):
        return END  # 信号生成任务完成
    
    return END
