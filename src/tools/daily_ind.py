# %%
"""
Tushare数据获取工具
提供LangChain工具来访问Tushare的各种数据接口
"""

import os
from typing import Optional, List, Dict, Any, Annotated
from langchain_core.tools import tool
import pandas as pd
from pathlib import Path

from ..state import GLOBAL_DATA_STATE


@tool("tushare_daily_basic")
def tushare_daily_basic_tool(
    ts_code: Annotated[str, "股票代码，例如：000001.SZ"] = None,
    trade_date: Annotated[Optional[str], "交易日期，格式YYYYMMDD，例如：20240101"] = None,
    start_date: Annotated[Optional[str], "开始日期，格式YYYYMMDD"] = None,
    end_date: Annotated[Optional[str], "结束日期，格式YYYYMMDD"] = None,
    fields: Annotated[Optional[str], "指定返回的字段，例如：'ts_code,trade_date,close,pe,pb'，如果为空则返回所有字段"] = None
) -> str:
    """获取股票每日基本面指标数据，包括市盈率、市净率、换手率等重要指标。
    
    输入参数：
    - ts_code: 股票代码（可选），例如：000001.SZ
    - trade_date: 交易日期（可选），格式YYYYMMDD，例如：20240101
    - start_date: 开始日期（可选），格式YYYYMMDD
    - end_date: 结束日期（可选），格式YYYYMMDD  
    - fields: 指定返回字段（可选），例如：'ts_code,trade_date,close,pe,pb'
    
    输出字段包括：
    - ts_code: TS股票代码
    - trade_date: 交易日期
    - close: 当日收盘价
    - turnover_rate: 换手率（%）
    - turnover_rate_f: 换手率（自由流通股）
    - volume_ratio: 量比
    - pe: 市盈率（总市值/净利润）
    - pe_ttm: 市盈率（TTM）
    - pb: 市净率（总市值/净资产）
    - ps: 市销率
    - ps_ttm: 市销率（TTM）
    - dv_ratio: 股息率（%）
    - dv_ttm: 股息率（TTM）（%）
    - total_share: 总股本（万股）
    - float_share: 流通股本（万股）
    - free_share: 自由流通股本（万）
    - total_mv: 总市值（万元）
    - circ_mv: 流通市值（万元）
    """
    try:
        # 从本地文件读取数据
        data_path = Path(__file__).parent.parent.parent / "data" / "20240901-20250901" / "daily_ind.parquet"
        
        if not data_path.exists():
            return f"错误：数据文件不存在 {data_path}"
        
        # 读取parquet文件
        df = pd.read_parquet(data_path)
        
        # 根据参数筛选数据
        if ts_code:
            df = df[df['ts_code'] == ts_code]
        
        if trade_date:
            df = df[df['trade_date'] == str(trade_date)]
        
        if start_date:
            df = df[df['trade_date'] >= str(start_date)]
        
        if end_date:
            df = df[df['trade_date'] <= str(end_date)]
        
        # 确定需要保留的字段（必须包含 ts_code 和 trade_date）
        base_fields = ['ts_code', 'trade_date']
        if fields:
            field_list = [f.strip() for f in fields.split(',')]
            # 数据字段（排除索引字段）
            data_fields = [f for f in field_list if f in df.columns and f not in base_fields]
        else:
            # 如果未指定字段，使用所有非索引字段
            data_fields = [col for col in df.columns if col not in base_fields]
        
        # 确保 DataFrame 包含必要的列
        required_cols = base_fields + data_fields
        df = df[required_cols]
        
        if df.empty:
            return "未找到符合条件的数据"
        
        # 对每个数据字段进行 pivot 转换并存入 GlobalDataState
        pivot_dfs = {}
        for field in data_fields:
            try:
                # pivot: index=trade_date, columns=ts_code, values=field
                pivot_df = df.pivot(index='trade_date', columns='ts_code', values=field)
                # 将 index 转换为日期格式以便排序
                pivot_df.index = pd.to_datetime(pivot_df.index, format='%Y%m%d')
                pivot_df = pivot_df.sort_index()
                pivot_dfs[field] = pivot_df
            except Exception as e:
                # 如果 pivot 失败（如有重复数据），记录错误但继续处理其他字段
                print(f"警告：字段 {field} pivot 失败: {str(e)}")
                continue
        
        # 将 pivot 后的 DataFrames 存入 GlobalDataState.indicators
        if pivot_dfs:
            GLOBAL_DATA_STATE.update('indicators', pivot_dfs)
        
        # 转换为JSON格式返回
        result = {
            "message": f"成功加载 {len(pivot_dfs)} 个指标到 GlobalDataState.indicators",
            "indicators": list(pivot_dfs.keys()),
            "shape": {field: {"rows": df.shape[0], "cols": df.shape[1]} 
                      for field, df in pivot_dfs.items()},
            "total_count": len(df),
        }
        
        return str(result)
        
    except Exception as e:
        return f"查询失败：{str(e)}"


def get_tushare_daily_basic_tool():
    """获取Tushare每日指标工具实例"""
    return tushare_daily_basic_tool


# 导出工具列表
def get_tushare_tools() -> List:
    """获取所有Tushare工具的列表"""
    return [tushare_daily_basic_tool]


# 导出工具实例
TUSHARE_TOOLS = [tushare_daily_basic_tool]