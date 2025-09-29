#!/usr/bin/env python3
"""
示例脚本：如何读取保存的con_code列表

这个脚本演示了如何从JSON文件中读取沪深300成分股代码列表
"""

import json
from pathlib import Path

def read_con_code_list(trade_date='20250901'):
    """
    读取指定交易日期的沪深300成分股代码列表
    
    Args:
        trade_date (str): 交易日期，格式为YYYYMMDD
        
    Returns:
        list: 成分股代码列表，按权重降序排列
    """
    # 构建文件路径
    json_filename = f"hs300_con_code_list_{trade_date}.json"
    json_path = Path('.') / json_filename
    
    try:
        # 读取JSON文件
        with open(json_path, 'r', encoding='utf-8') as f:
            con_code_list = json.load(f)
        
        print(f"成功读取 {len(con_code_list)} 个成分股代码")
        return con_code_list
        
    except FileNotFoundError:
        print(f"文件不存在: {json_path}")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        return []
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return []

if __name__ == "__main__":
    # 示例用法
    trade_date = '20250901'
    
    print(f"正在读取 {trade_date} 的沪深300成分股列表...")
    con_codes = read_con_code_list(trade_date)
    
    if con_codes:
        print(f"\n前10个成分股代码（按权重降序）:")
        for i, code in enumerate(con_codes[:10], 1):
            print(f"{i:2d}. {code}")
        
        print(f"\n后10个成分股代码:")
        for i, code in enumerate(con_codes[-10:], len(con_codes)-9):
            print(f"{i:2d}. {code}")
        
        # 演示如何使用这个列表
        print(f"\n使用示例:")
        print(f"# 获取所有成分股代码")
        print(f"all_codes = {con_codes[:3]}...  # 共{len(con_codes)}个")
        
        print(f"\n# 检查某个股票是否在成分股中")
        test_code = con_codes[0] if con_codes else "600519.SH"
        print(f"'{test_code}' in con_codes: {test_code in con_codes}")
        
        print(f"\n# 获取权重排名前N的股票")
        top_n = 5
        print(f"top_{top_n}_codes = con_codes[:{top_n}]")
        print(f"结果: {con_codes[:top_n]}")
        
    else:
        print("未能读取到数据")
