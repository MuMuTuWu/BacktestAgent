# Reflection Node 架构重构总结

## 📋 重构目标
优化 `reflection_node` 的架构，将 `next_action_desc` 从结构化的 dict 改为自然语言字符串，充分利用 LLM 的文本理解能力。

---

## 🔄 核心改变

### 1. State 类型变更（state.py）
```python
# 改前
next_action_desc: dict  # 包含：{type: str, params: dict}

# 改后
next_action_desc: str   # 自然语言描述，包含具体的任务参数或策略逻辑
```

---

### 2. Reflection Node 架构重构（reflection.py）

#### 2.1 Prompt 分离
将原来的单一 `REFLECTION_NODE_PROMPT` 拆分为两部分：

**System Prompt（系统级指令）**
- `REFLECTION_SYSTEM_PROMPT`：包含角色定义、next_action 决策规则、next_action_desc 编写指南
- 定义了四个 action 的选择条件和 next_action_desc 的编写标准
- 包含 JSON 输出格式示例

**User Message Template（用户级消息）**
- `REFLECTION_USER_PROMPT_TEMPLATE`：包含可用工具、当前状态、执行历史、错误信息等动态内容
- 包含用户请求的具体内容
- 提供执行指南

#### 2.2 Messages 架构
```python
# 改前
messages = [{"role": "user", "content": prompt}]

# 改后
messages = [
    {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
    {"role": "user", "content": user_message}
]
```

#### 2.3 Retry Count 更新
在 reflection_node 中添加了 retry_count 递增逻辑，用于追踪重试次数。

---

### 3. Data Fetch 节点优化（data_fetch.py）

#### 3.1 Prompt 改进
将 prompt 中的参数填充改为：
```python
# 改前
prompt = DATA_FETCH_AGENT_PROMPT.format(
    ts_code=ts_code,
    start_date=start_date,
    end_date=end_date,
    required_indicators=required_indicators
)

# 改后
prompt = DATA_FETCH_AGENT_PROMPT.format(
    next_action_desc=next_action_desc
)
```

#### 3.2 Agent 赋权
Data fetch agent 现在直接在 prompt 中接收完整的任务描述，可以自主理解和提取：
- 股票代码（格式：000001.SZ）
- 时间范围（格式：YYYYMMDD）
- 所需指标列表

#### 3.3 简化参数提取
```python
# 改前
params = state.get('next_action_desc', {}).get('params', {})
ts_code = params.get('ts_code', '未指定')
start_date = params.get('start_date', '未指定')
end_date = params.get('end_date', '未指定')
required_indicators = params.get('required_indicators', [])

# 改后
next_action_desc = state.get('next_action_desc', '未指定任务')
# 直接传给 agent 理解
```

---

### 4. Signal Generate 节点优化（signal_generate.py）

#### 4.1 策略描述来源
```python
# 改前
params = state.get('next_action_desc', {}).get('params', {})
strategy_description = params.get('strategy_desc', '未指定策略')

# 改后
strategy_description = state.get('next_action_desc', '未指定策略')
```

#### 4.2 直接使用
signal_generate 节点现在直接使用 `next_action_desc` 作为完整的策略描述，无需解构 params。

---

### 5. Routes 简化（routes.py）

#### 5.1 route_after_validation 改进
```python
# 改前
intent_type = state.get('next_action_desc', {}).get('type')
if intent_type == 'data_fetch' and state.get('data_ready'):
    return END
if intent_type == 'signal_gen' and state.get('signal_ready'):  # 注意：是 'signal_gen'
    return END
if intent_type == 'mixed':
    if state.get('data_ready') and state.get('signal_ready'):
        return END
    else:
        return 'reflection'

# 改后
next_action = state.get('next_action', 'end')
if next_action == 'data_fetch' and state.get('data_ready'):
    return END
if next_action == 'signal_generate' and state.get('signal_ready'):
    return END
return END
```

#### 5.2 依赖关系简化
路由现在直接依赖 `next_action` 字段，不再耦合 `next_action_desc` 结构。

---

## 📝 next_action_desc 编写规范

### 当 next_action="data_fetch" 时
自然语言应该清晰表达：
- **股票代码**（如：000001.SZ）
- **时间范围**（如：20240101 到 20240630）
- **数据类型**（OHLCV + 指标）
- **具体指标**（如：pe, pb, turnover_rate）

**示例：**
```
获取000001.SZ从20240101到20240630的日线OHLCV数据，同时获取pe和pb估值指标
```

### 当 next_action="signal_generate" 时
自然语言应该描述完整的策略逻辑：
- **策略类型**
- **数据需求**
- **信号定义**（买入/卖出/持有条件）

**示例：**
```
基于5日和20日均线交叉生成信号：当5日均线上穿20日均线时买入（信号值=1），下穿时卖出（信号值=-1），其他时间持有（信号值=0）
```

### 当 next_action="validate" 时
说明验证的目标和重点：

**示例：**
```
验证数据完整性：检查OHLCV数据是否有缺失，指标数据的行数是否与行情数据对齐
```

---

## ✅ 验证清单

- [x] state.py：next_action_desc 改为 str 类型
- [x] reflection.py：prompt 分离为 REFLECTION_SYSTEM_PROMPT 和 REFLECTION_USER_PROMPT_TEMPLATE
- [x] reflection_node：支持 system + user message，添加 retry_count 更新
- [x] data_fetch.py：agent 直接在 prompt 中理解 next_action_desc
- [x] signal_generate.py：直接使用 next_action_desc 作为策略描述
- [x] routes.py：使用 next_action 而非 next_action_desc.type
- [x] 所有文件通过 linter 检查
- [x] Git commit 完成

---

## 🎯 重构优势

| 优势项 | 说明 |
|------|------|
| **结构简化** | next_action_desc 由嵌套 dict 改为单一字符串，代码更清晰 |
| **LLM友好** | 充分利用 LLM 的自然语言理解能力，比结构化 params 更灵活 |
| **参数提取** | 下游节点 agent 自动提取参数，无需手动解构 |
| **维护性** | 减少状态耦合，路由逻辑更简洁 |
| **可读性** | next_action_desc 采用自然语言，更易理解和调试 |
| **扩展性** | 新增 action 无需修改 state 结构，只需更新 prompt |

---

## 🔗 文件变更统计

```
 5 files changed, 141 insertions(+), 116 deletions(-)
 - state.py
 - reflection.py（+prompt 分离）
 - data_fetch.py
 - signal_generate.py
 - routes.py
```

---

**重构完成于：2025-10-16**
