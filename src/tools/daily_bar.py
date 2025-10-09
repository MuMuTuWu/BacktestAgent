"""
LangChain工具：获取A股日线行情（从本地parquet文件读取）
"""

from typing import Optional, List, Dict, Any, Annotated
from pathlib import Path

import pandas as pd
from langchain_core.tools import tool

from ..state import GLOBAL_DATA_STATE


@tool("tushare_daily_bar")
def tushare_daily_bar_tool(
    ts_code: Annotated[str, "股票代码，例如：000001.SZ"] = None,
    start_date: Annotated[Optional[str], "开始日期，格式YYYYMMDD"] = None,
    end_date: Annotated[Optional[str], "结束日期，格式YYYYMMDD"] = None,
) -> str:
    """获取A股日线行情数据（OHLCV）。

    输入参数：
    - ts_code: 股票代码（可选），例如：000001.SZ
    - start_date: 开始日期（可选），格式YYYYMMDD
    - end_date: 结束日期（可选），格式YYYYMMDD
    
    核心字段包括：ts_code、trade_date、open、high、low、close、vol（成交量）。
    数据会被pivot转换后存入GlobalDataState.ohlcv，每个字段一个DataFrame。
    """
    try:
        # 从本地文件读取数据
        data_path = Path(__file__).parent.parent.parent / "data" / "20240901-20250901" / "hs300_pro_bar_daily.parquet"
        
        if not data_path.exists():
            return f"错误：数据文件不存在 {data_path}"
        
        # 读取parquet文件
        df = pd.read_parquet(data_path)
        
        # 根据参数筛选数据
        if ts_code:
            df = df[df['ts_code'] == ts_code]
        
        if start_date:
            df = df[df['trade_date'] >= str(start_date)]
        
        if end_date:
            df = df[df['trade_date'] <= str(end_date)]
        
        if df.empty:
            return "未找到符合条件的数据"
        
        # OHLCV字段
        ohlcv_fields = ['open', 'high', 'low', 'close', 'vol']
        base_fields = ['ts_code', 'trade_date']
        
        # 确保 DataFrame 包含必要的列
        required_cols = base_fields + ohlcv_fields
        df = df[required_cols]
        
        # 对每个OHLCV字段进行 pivot 转换并存入 GlobalDataState.ohlcv
        pivot_dfs = {}
        for field in ohlcv_fields:
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
        
        # 将 pivot 后的 DataFrames 存入 GlobalDataState.ohlcv
        if pivot_dfs:
            GLOBAL_DATA_STATE.update('ohlcv', pivot_dfs)
        
        # 转换为JSON格式返回
        result = {
            "message": f"成功加载 {len(pivot_dfs)} 个OHLCV字段到 GlobalDataState.ohlcv",
            "fields": list(pivot_dfs.keys()),
            "shape": {field: {"rows": df.shape[0], "cols": df.shape[1]} 
                      for field, df in pivot_dfs.items()},
            "total_count": len(df),
        }
        
        return str(result)

    except Exception as exc:  # pylint: disable=broad-except
        return f"查询失败：{exc}"


def get_tushare_daily_bar_tool():
    """获取日线行情工具实例"""
    return tushare_daily_bar_tool


def get_tushare_tools() -> List:
    """获取所有已注册的日线行情相关工具"""
    return [tushare_daily_bar_tool]


TUSHARE_TOOLS = [tushare_daily_bar_tool]
