"""
信号生成子图的路由函数
"""
from langgraph.graph import END
from .state import SignalSubgraphState


def route_from_reflection(state: SignalSubgraphState) -> str:
    """从反思节点出发的路由决策"""
    
    # 优先处理澄清
    if state.get('clarification_needed'):
        return 'clarify'
    
    # 根据用户意图类型决策
    intent_type = state.get('user_intent', {}).get('type')
    
    if intent_type == 'data_fetch':
        return 'data_fetch'
    
    if intent_type == 'signal_gen':
        # 检查数据是否就绪
        if not state.get('data_ready'):
            return 'data_fetch'  # 先获取数据
        return 'signal_generate'
    
    if intent_type == 'mixed':
        # 混合任务，先获取数据
        if not state.get('data_ready'):
            return 'data_fetch'
        # 数据就绪，生成信号
        if not state.get('signal_ready'):
            return 'signal_generate'
    
    # 如果信号已生成，进行验证
    if state.get('signal_ready'):
        return 'validate'
    
    # 所有任务完成
    if state.get('data_ready') and intent_type == 'data_fetch':
        return 'validate'
    
    return END


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
            # 多次失败，请求澄清
            return 'clarify'
    
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
            # 无法自动修复
            return 'clarify'
    
    # 验证通过，检查任务完成状态
    intent_type = state.get('user_intent', {}).get('type')
    
    if intent_type == 'data_fetch' and state.get('data_ready'):
        return END  # 数据获取任务完成
    
    if intent_type == 'signal_gen' and state.get('signal_ready'):
        return END  # 信号生成任务完成
    
    if intent_type == 'mixed':
        if state.get('data_ready') and state.get('signal_ready'):
            return END  # 混合任务完成
        else:
            return 'reflection'  # 继续下一阶段
    
    return END


def route_after_clarify(state: SignalSubgraphState) -> str:
    """澄清后的路由"""
    # 重新评估用户意图
    return 'reflection'
