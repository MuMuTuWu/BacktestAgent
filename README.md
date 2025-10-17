# BacktestAgent

基于 LangGraph 的量化交易策略回测智能体系统。该项目通过多个子图协同工作，实现从数据获取、信号生成到策略回测的完整自动化流程。

## 🌟 项目特点

- **模块化设计**：采用 LangGraph 子图架构，信号生成和回测功能独立可复用
- **智能路由**：基于 ReAct 模式的反思节点，自动识别任务状态并智能调度
- **数据获取**：集成 Tushare API，支持 OHLCV 行情数据和技术指标获取
- **策略回测**：基于 vectorbt 框架执行高性能回测
- **可视化报告**：使用 quantstats 生成专业的 HTML 策略分析报告
- **日志记录**：完整的执行日志，支持 JSONL 和文本格式

## 📁 项目结构

```
BacktestAgent/
├── src/
│   ├── subgraphs/
│   │   ├── signal/          # 信号生成子图
│   │   │   ├── nodes/       # 数据获取、信号生成、验证等节点
│   │   │   ├── graph.py     # 子图定义
│   │   │   ├── routes.py    # 路由逻辑
│   │   │   └── state.py     # 状态定义
│   │   └── backtest/        # 回测子图
│   │       ├── nodes/       # 回测、PNL绘图、反思等节点
│   │       ├── graph.py     # 子图定义
│   │       ├── routes.py    # 路由逻辑
│   │       └── state.py     # 状态定义
│   ├── tools/               # 工具函数（数据获取等）
│   ├── utils/               # 工具类（日志记录等）
│   ├── llm.py              # LLM配置
│   └── state.py            # 全局状态管理
├── data/                    # 数据文件和脚本
├── docs/                    # 文档
├── notebook/               # Jupyter Notebook 示例
├── output/                 # 输出目录（按日期组织）
├── main.py               # 主图执行入口
├── src/config.py          # 配置文件（已从根目录迁移）
└── pyproject.toml         # 项目依赖

```

## 🚀 快速开始

### 环境要求

- Python >= 3.12
- uv（Python 包管理工具）

### 安装

1. 克隆仓库：
```bash
git clone https://github.com/MuMuTuWu/BacktestAgent.git
cd BacktestAgent
```

2. 激活 uv 虚拟环境：
```bash
source .venv/bin/activate
```

3. 安装依赖：
```bash
uv sync
```

4. 配置环境变量：

创建 `.env` 文件并配置以下变量：
```bash
# OpenAI API配置
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=your_openai_base_url  # 可选

# Tushare API配置
TUSHARE_TOKEN=your_tushare_token
```

### 基本使用

#### 1. 运行完整流程（信号生成 + 回测）

```bash
uv run main.py
```

#### 2. 仅运行信号生成子图

```python
from src.subgraphs.signal import build_signal_graph, SignalSubgraphState

graph = build_signal_graph().compile()

initial_state: SignalSubgraphState = {
    "messages": [
        {"role": "user", "content": "请获取000001.SZ从20240901到20240930的数据"}
    ],
    "current_task": "",
    "data_ready": False,
    "indicators_ready": False,
    "signal_ready": False,
    "user_intent": {},
    "clarification_needed": None,
    "clarification_count": 0,
    "execution_history": [],
    "error_messages": [],
    "max_retries": 3,
    "retry_count": 0,
}

result = graph.invoke(initial_state)
```

#### 3. 仅运行回测子图

```python
from src.subgraphs.backtest import build_backtest_graph, BacktestSubgraphState

# 假设signal已存在于GLOBAL_DATA_STATE中
graph = build_backtest_graph().compile()

initial_state: BacktestSubgraphState = {
    "messages": [
        {"role": "user", "content": "请对现有信号执行回测"}
    ],
    "current_task": "",
    "signal_ready": True,
    "backtest_completed": False,
    "returns_ready": False,
    "pnl_plot_ready": False,
    "backtest_params": {
        "init_cash": 100000,
        "fees": 0.001,
        "slippage": 0.0
    },
    "execution_history": [],
    "error_messages": [],
    "max_retries": 3,
    "retry_count": 0,
}

result = graph.invoke(initial_state)
```

## 🧩 核心组件

### 信号生成子图 (Signal Subgraph)

负责从数据获取到交易信号生成的完整流程：

- **数据获取节点**：调用 Tushare API 获取 OHLCV 和技术指标数据
- **信号生成节点**：基于用户策略描述生成交易信号
- **验证节点**：确保数据和信号的质量
- **反思节点**：智能识别用户意图并调度任务
- **澄清节点**：信息不足时触发 human-in-the-loop

详细文档：[src/subgraphs/signal/README.md](src/subgraphs/signal/README.md)

### 回测子图 (Backtest Subgraph)

负责对交易信号执行回测并生成报告：

- **回测节点**：使用 vectorbt 执行高性能回测
- **PNL绘图节点**：使用 quantstats 生成 HTML 分析报告
- **反思节点**：检查回测质量，必要时重跑

详细文档：[src/subgraphs/backtest/README.md](src/subgraphs/backtest/README.md)

## 📊 输出说明

所有输出文件按日期和任务编号组织在 `output/` 目录下：

```
output/
└── 2025-10-10/          # 日期目录
    ├── task-1/          # 任务目录
    │   ├── execution_log.jsonl    # JSONL格式日志
    │   ├── execution_log.txt      # 文本格式日志
    │   ├── strategy_report.html   # 策略分析报告（如有回测）
    │   └── summary.json           # 任务摘要（如有）
    └── task-2/
        └── ...
```

## 🛠️ 技术栈

- **LangGraph**：工作流编排和状态管理
- **LangChain**：LLM集成和工具调用
- **vectorbt**：高性能量化回测框架
- **quantstats**：策略性能分析和可视化
- **Tushare**：金融数据接口
- **OpenAI API**：大语言模型服务

## 📖 文档

- [信号生成子图设计](docs/signal_subgraph_design.md)
- [流式模式使用指南](docs/stream_modes_guide.md)
- [调试输出来源](docs/debug_output_source.md)
- [Tushare API文档](docs/)

## 🔧 开发指南

### 运行测试

```bash
# 测试信号生成子图
uv run notebook/test_signal_subgraph.py

# 测试回测子图
uv run notebook/test_backtest_subgraph.py
```

### 生成流程图

```bash
uv run generate_mermaid.py
```

这将生成子图的 Mermaid 流程图文件。

## 📝 注意事项

1. **环境管理**：本项目统一使用 `uv` 管理依赖，禁止使用 `pip`
2. **Python运行**：执行 Python 脚本时必须使用 `uv run <脚本路径>`
3. **虚拟环境**：运行命令前需先激活项目虚拟环境：`source .venv/bin/activate`
4. **数据缓存**：数据文件存储在 `data/` 目录，避免重复下载
5. **日志记录**：所有执行过程都会记录到 `output/` 目录
