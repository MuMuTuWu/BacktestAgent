# BacktestAgent 状态与图转移设计说明

## 参考工程的启发

Gemini Fullstack LangGraph Quickstart 提供了一个干净的分层范式：
- **单一入口状态**：`OverallState` 承载消息流（通过 `add_messages` 聚合）以及循环控制字段，其子流程仅暴露自己需要的增量片段。
- **轻量子状态**：`QueryGenerationState`、`WebSearchState`、`ReflectionState` 等只关注自身输入输出，字段命名贴近业务而非框架术语。
- **显式路由函数**：条件边只返回有限的目标标识或使用 `Send` 批量派发，避免在节点内部耦合流程。
- **逐步收敛**：研究环内的节点会递增 `research_loop_count`，再由路由器基于阈值决定继续还是终止，流程意图明显。

这一模式实现了“主状态负责汇总、子节点各管一段”的最小完备设计，对初学者十分友好。

## BacktestAgent 现状痛点

- 主图 `MainGraphState` 额外维护 `signal_context`、`backtest_context` 等深层嵌套结构，状态传递不直观。
- 子图状态与主图高度耦合，不便于复用或单测；错误收集逻辑散落在合并函数中。
- 条件路由依赖大量布尔标记（例如 `signal_ready`），但节点的职责没有和标记形成“一对一”关系，阅读成本高。

## 设计目标

1. **状态聚焦**：保留消息与核心控制字段，其余信息放在对应子流程的增量状态中。
2. **清晰路由**：用返回枚举字符串或 `Send` 描述下一步，避免布尔条件散落。
3. **一致命名**：字段名直观表达业务含义，如 `signal_status`、`backtest_report`。
4. **最少魔法**：遵循 LangGraph 默认行为（TypedDict + `add_messages`），不上复杂抽象，适合教学与维护。

## 新方案概览

- **主状态 `WorkflowState`**
  - 聚合消息与跨子图的基础标记（`signal_finished`、`backtest_finished`）。
  - 保存两段结构化结果：`signal_summary` 与 `backtest_summary`，方便最终汇总。
- **信号子图**
  - 状态 `SignalState` 只保留数据就绪标记、生成结果与重试计数。
  - 路由函数根据数据准备情况选择 `fetch_data`、`generate_signal`、`clarify_intent` 等节点。
- **回测子图**
  - 状态 `BacktestState` 管理任务列表、回测输出、图表生成标记。
  - 路由函数根据回测是否完成决定是否生成报表或终止。
- **主图调度**
  - 入口始终调用信号子图，收到 `signal_finished=True` 才进入回测子图。
  - 主图合并函数仅负责把子图返回的增量写入顶层结构，再由路由函数决定是否结束。

最终得到的主图/子图流转路径简洁清晰，既保留 LangGraph 的最佳实践，也让新同事易于理解和扩展。
