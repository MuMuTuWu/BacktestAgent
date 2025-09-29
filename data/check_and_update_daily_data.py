#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查和更新沪深300每日指标数据

功能：
1. 检查是否已存在daily_ind.parquet文件
2. 如果存在，比较现有数据中的ts_code与权重文件中的con_code，找出缺失的股票
3. 下载缺失股票的数据
4. 合并现有数据和新数据，保存为新的parquet文件
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import time
import threading
import json
import warnings
warnings.filterwarnings('ignore')

# 添加项目路径
sys.path.append('..')

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 导入项目工具
from src.tools.utils import _init_tushare_api


def fetch_stock_daily_basic(ts_code, start_date, end_date, retry_count=3):
    """
    获取单只股票的每日指标数据
    
    Args:
        ts_code: 股票代码
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
        retry_count: 重试次数
    
    Returns:
        DataFrame: 该股票的每日指标数据
    """
    for attempt in range(retry_count):
        try:
            # 调用Tushare API
            df = pro.daily_basic(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            
            # 在每次API调用后添加延迟，避免过于频繁的请求
            time.sleep(0.2)
            
            if not df.empty:
                return df
            else:
                print(f"⚠️  {ts_code}: 无数据")
                return pd.DataFrame()
                
        except Exception as e:
            error_msg = str(e)
            if "每分钟最多访问该接口200次" in error_msg:
                # 如果遇到速率限制错误，等待更长时间
                print(f"⚠️  {ts_code}: API速率限制，等待60秒后重试...")
                time.sleep(60)
            elif attempt < retry_count - 1:
                print(f"⚠️  {ts_code}: 第{attempt+1}次尝试失败 ({e})，重试中...")
                time.sleep(2)  # 等待2秒后重试
            else:
                print(f"✗ {ts_code}: 获取失败 - {e}")
                return pd.DataFrame()
    
    return pd.DataFrame()


def main():
    print("开始检查和更新沪深300每日指标数据...")
    
    # 初始化配置
    print("初始化配置...")
    
    # 从环境变量获取时间范围
    start_date_str = os.getenv('START_DATE', '20240901')
    end_date_str = os.getenv('END_DATE', '20250901')
    
    print(f"开始日期: {start_date_str}")
    print(f"结束日期: {end_date_str}")
    
    # 初始化Tushare API
    global pro
    try:
        pro = _init_tushare_api()
        print("✓ Tushare API 初始化成功")
    except Exception as e:
        print(f"✗ Tushare API 初始化失败: {e}")
        raise
    
    # 读取沪深300成分股代码
    print("读取沪深300成分股代码...")
    
    json_file = Path('hs300_con_code_list_20250901.json')
    if not json_file.exists():
        raise FileNotFoundError(f"找不到文件: {json_file}")
    
    # 读取JSON文件
    with open(json_file, 'r', encoding='utf-8') as f:
        con_code_list = json.load(f)
    print(f"读取到 {len(con_code_list)} 个成分股代码")
    
    # 转换为集合
    all_stock_codes = set(con_code_list)
    print(f"沪深300成分股数量: {len(all_stock_codes)}")
    
    # 检查是否存在现有数据文件
    save_dir = Path(f"{start_date_str}-{end_date_str}")
    save_path = save_dir / "daily_ind.parquet"
    
    existing_data = pd.DataFrame()
    existing_stock_codes = set()
    
    if save_path.exists():
        print(f"找到现有数据文件: {save_path}")
        try:
            existing_data = pd.read_parquet(save_path)
            existing_stock_codes = set(existing_data['ts_code'].unique())
            print(f"现有数据包含 {len(existing_stock_codes)} 只股票")
            print(f"现有数据形状: {existing_data.shape}")
            print(f"现有数据日期范围: {existing_data['trade_date'].min()} - {existing_data['trade_date'].max()}")
        except Exception as e:
            print(f"读取现有数据文件失败: {e}")
            existing_data = pd.DataFrame()
            existing_stock_codes = set()
    else:
        print("未找到现有数据文件，将下载全部数据")
    
    # 找出缺失的股票代码
    missing_stock_codes = all_stock_codes - existing_stock_codes
    
    print(f"\n股票代码比较结果:")
    print(f"目标股票总数: {len(all_stock_codes)}")
    print(f"现有股票数量: {len(existing_stock_codes)}")
    print(f"缺失股票数量: {len(missing_stock_codes)}")
    
    if missing_stock_codes:
        print(f"缺失的股票代码前10个: {list(missing_stock_codes)[:10]}")
        
        # 下载缺失的股票数据
        print(f"\n开始下载 {len(missing_stock_codes)} 只缺失股票的数据...")
        
        # 存储新下载的数据
        new_data = []
        failed_stocks = []
        
        # 调整线程数
        max_workers = 2  # 使用适量的并发数
        print(f"使用 {max_workers} 个工作线程")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_stock = {
                executor.submit(fetch_stock_daily_basic, stock_code, start_date_str, end_date_str): stock_code
                for stock_code in missing_stock_codes
            }
            
            # 使用tqdm显示进度
            with tqdm(total=len(missing_stock_codes), desc="下载进度", 
                      bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
                
                for future in as_completed(future_to_stock):
                    stock_code = future_to_stock[future]
                    try:
                        df_stock = future.result()
                        if not df_stock.empty:
                            new_data.append(df_stock)
                            pbar.set_postfix({
                                "成功": len(new_data), 
                                "失败": len(failed_stocks)
                            })
                        else:
                            failed_stocks.append(stock_code)
                            pbar.set_postfix({
                                "成功": len(new_data), 
                                "失败": len(failed_stocks)
                            })
                    except Exception as e:
                        failed_stocks.append(stock_code)
                        print(f"✗ {stock_code}: 处理异常 - {e}")
                        pbar.set_postfix({
                            "成功": len(new_data), 
                            "失败": len(failed_stocks)
                        })
                    
                    pbar.update(1)
                    
                    # 在每次获取后添加短暂延迟
                    time.sleep(0.1)
        
        print(f"\n新数据下载完成!")
        print(f"成功下载: {len(new_data)} 只股票")
        print(f"下载失败: {len(failed_stocks)} 只股票")
        
        if failed_stocks:
            print(f"失败的股票代码: {failed_stocks[:10]}{'...' if len(failed_stocks) > 10 else ''}")
        
        # 合并现有数据和新数据
        if new_data:
            print("\n合并现有数据和新下载的数据...")
            
            # 将新数据合并为DataFrame
            df_new = pd.concat(new_data, ignore_index=True)
            print(f"新下载数据形状: {df_new.shape}")
            
            # 合并现有数据和新数据
            if not existing_data.empty:
                df_combined = pd.concat([existing_data, df_new], ignore_index=True)
                print(f"合并后数据形状: {df_combined.shape}")
            else:
                df_combined = df_new
                print(f"仅新数据，数据形状: {df_combined.shape}")
            
            # 去重（以防万一）
            original_shape = df_combined.shape
            df_combined = df_combined.drop_duplicates(subset=['ts_code', 'trade_date'])
            if df_combined.shape != original_shape:
                print(f"去重后数据形状: {df_combined.shape}")
            
            # 保存合并后的数据
            print("\n保存合并后的数据...")
            
            # 创建保存目录
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 先保存CSV格式（更稳定）
            csv_path = save_dir / "daily_ind.csv"
            df_combined.to_csv(csv_path, index=False)
            print(f"✓ 数据已保存为CSV格式到: {csv_path}")
            print(f"CSV文件大小: {csv_path.stat().st_size / 1024 / 1024:.2f} MB")
            
            # 再保存parquet文件
            try:
                df_combined.to_parquet(save_path, index=False)
                print(f"✓ 数据已保存为parquet格式到: {save_path}")
                print(f"parquet文件大小: {save_path.stat().st_size / 1024 / 1024:.2f} MB")
                
                # 验证保存的数据
                df_verify = pd.read_parquet(save_path)
                print(f"验证: 保存的数据形状为 {df_verify.shape}")
                print(f"包含股票数量: {df_verify['ts_code'].nunique()}")
                print(f"日期范围: {df_verify['trade_date'].min()} - {df_verify['trade_date'].max()}")
            except Exception as e:
                print(f"⚠️ parquet保存失败: {e}")
                print("但CSV文件已成功保存")
            
            # 最终统计报告
            print("\n" + "=" * 50)
            print("最终数据统计报告")
            print("=" * 50)
            
            final_stock_count = df_combined['ts_code'].nunique()
            success_rate = final_stock_count / len(all_stock_codes) * 100
            
            print(f"目标股票数量: {len(all_stock_codes)}")
            print(f"最终股票数量: {final_stock_count}")
            print(f"数据完整率: {success_rate:.1f}%")
            print(f"总数据记录数: {len(df_combined)}")
            
            # 检查仍然缺失的股票
            final_stock_codes = set(df_combined['ts_code'].unique())
            still_missing = all_stock_codes - final_stock_codes
            
            if still_missing:
                print(f"仍然缺失的股票数量: {len(still_missing)}")
                print(f"仍然缺失的股票代码: {list(still_missing)[:10]}{'...' if len(still_missing) > 10 else ''}")
            else:
                print("✓ 所有目标股票数据都已获取完整")
            
        else:
            print("⚠️ 未能下载到任何新数据")
            
    else:
        print("✓ 所有股票数据都已存在，无需下载新数据")
        
        if not existing_data.empty:
            print(f"\n现有数据统计:")
            print(f"股票数量: {existing_data['ts_code'].nunique()}")
            print(f"总记录数: {len(existing_data)}")
            print(f"日期范围: {existing_data['trade_date'].min()} - {existing_data['trade_date'].max()}")
    
    print("\n✓ 数据检查和更新任务完成！")


if __name__ == "__main__":
    main()
