```mermaid
flowchart TD
  START([START]) --> R[ReflectRouter\n解析意图/提取参数/检查 GLOBAL_DATA_STATE]

  R -->|参数缺失| C[ClarifyParams\n向用户澄清/更新 params]
  C --> R

  subgraph AG_FETCH [FetchDataAgent（ReAct 工具代理）]
    direction TB
    F1[tushare_daily_bar_tool\n-> GLOBAL_DATA_STATE.ohlcv]:::tool
    F2[tushare_daily_basic_tool\n-> GLOBAL_DATA_STATE.indicators]:::tool
  end

  R -->|数据缺失(ohlcv/indicators)| AG_FETCH
  AG_FETCH --> R

  subgraph AG_BUILD [BuildSignalAgent（ReAct + REPL）]
    direction TB
    B1[PythonAstREPLTool\nglobals: {ohlcv, indicators, pd, np}\n产出: signal(DataFrame)]:::tool
  end

  R -->|数据就绪| AG_BUILD
  AG_BUILD --> S[SaveSignal\n写入 GLOBAL_DATA_STATE.signal]
  S --> V[ValidateAndFinish\n校验形状/值域/覆盖率]
  V -->|通过| END([END])
  V -->|失败或需调整| R

  classDef tool fill:#eef,stroke:#66f,stroke-width:1px;

```