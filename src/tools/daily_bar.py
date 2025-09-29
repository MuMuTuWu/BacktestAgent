"""
LangChain工具：获取A股日线行情（通过Tushare pro_bar接口）
"""

from typing import Optional, List, Dict, Any, Annotated

import pandas as pd
import tushare as ts
from langchain_core.tools import tool

from .utils import _init_tushare_api


def _parse_comma_separated(value: Optional[str]) -> Optional[List[str]]:
    """将逗号分隔的字符串转换为字符串列表"""
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _parse_ma_list(value: Optional[str]) -> Optional[List[int]]:
    """将逗号分隔的字符串转换为整数列表，用于ma参数"""
    items = _parse_comma_separated(value)
    if not items:
        return None
    ma_values: List[int] = []
    for item in items:
        try:
            ma_values.append(int(item))
        except ValueError as exc:
            raise ValueError(f"ma参数必须是整数，无法解析：{item}") from exc
    return ma_values


def _parse_bool(value: Any) -> Optional[bool]:
    """解析布尔参数，支持bool与字符串形式"""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    raise ValueError(f"无法解析布尔值：{value}")


@tool("tushare_daily_bar")
def tushare_daily_bar_tool(
    ts_code: Annotated[str, "股票代码，例如：000001.SZ"] = "",
    start_date: Annotated[Optional[str], "开始日期，格式YYYYMMDD"] = None,
    end_date: Annotated[Optional[str], "结束日期，格式YYYYMMDD"] = None,
    trade_date: Annotated[Optional[str], "单个交易日，格式YYYYMMDD"] = None,
    adj: Annotated[Optional[str], "复权类型：None/qfq/hfq"] = None,
    asset: Annotated[str, "资产类别，股票默认E"] = "E",
    freq: Annotated[str, "数据频度，默认D(日线)"] = "D",
    ma: Annotated[Optional[str], "均线参数，逗号分隔，例如：'5,10,20'"] = None,
    factors: Annotated[Optional[str], "股票因子，逗号分隔，例如：'tor,vr'"] = None,
    adjfactor: Annotated[Optional[Any], "是否返回复权因子，True/False"] = False,
) -> str:
    """调用Tushare的pro_bar接口，获取A股日线行情数据。

    核心字段包括：ts_code、trade_date、open、high、low、close、pre_close、change、pct_chg、vol、amount。
    支持传入trade_date快速获取某一交易日的行情，详细参数说明参考docs/daily.md与docs/pro_bar.md。
    """
    try:
        if not ts_code:
            return "错误：ts_code为必填参数"

        # 确保已初始化Tushare token
        _init_tushare_api()

        params: Dict[str, Any] = {
            "ts_code": ts_code,
            "asset": asset or "E",
            "freq": freq or "D",
        }

        if trade_date and (start_date or end_date):
            return "错误：trade_date不能与start_date或end_date同时使用"

        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if trade_date:
            params["start_date"] = trade_date
            params["end_date"] = trade_date
        if adj:
            params["adj"] = adj

        parsed_adjfactor = _parse_bool(adjfactor)
        if parsed_adjfactor is not None:
            params["adjfactor"] = parsed_adjfactor

        ma_list = _parse_ma_list(ma)
        if ma_list:
            params["ma"] = ma_list

        factors_list = _parse_comma_separated(factors)
        if factors_list:
            params["factors"] = factors_list

        df = ts.pro_bar(**params)

        if df is None or df.empty:
            return "未找到符合条件的数据"

        df = df.reset_index()
        if "trade_date" in df.columns:
            df = df.sort_values("trade_date", ignore_index=True)

        result = {
            "data": df.to_dict("records"),
            "total_count": len(df),
            "columns": list(df.columns),
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
