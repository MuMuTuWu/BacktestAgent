# %% [markdown]
# # 沪深300指数成分和权重获取
# 
# 本notebook演示如何使用Tushare API获取沪深300指数的成分股和权重信息。
# 
# 根据 `docs/指数成分和权重.md` 的说明：
# - 接口：index_weight
# - 描述：获取各类指数成分和权重，**月度数据**
# - 建议输入参数里开始日期和结束日分别输入当月第一天和最后一天的日期
# - 用户需要至少2000积分才可以调取
# 

# %%
# 导入必要的模块
import sys
import os
import json
from datetime import datetime, date
from pathlib import Path

# 由于现在在data目录下，需要添加项目根目录到路径
current_dir = Path.cwd()
project_root = current_dir.parent
sys.path.append(str(project_root))

print(f"当前目录: {current_dir}")
print(f"项目根目录: {project_root}")
print(f"Python路径: {sys.path[-1]}")

import pandas as pd
import tushare as ts
from src.tools.utils import _init_tushare_api

# %% [markdown]
# ## 1. 初始化Tushare API
# 
# 首先需要确保TUSHARE_TOKEN环境变量已设置。
# 

# %%
# 初始化Tushare API
try:
    pro = _init_tushare_api()
    print("Tushare API 初始化成功")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
except Exception as e:
    print(f"Tushare API 初始化失败: {e}")
    print("请确保已设置TUSHARE_TOKEN环境变量")


# %% [markdown]
# ## 2. 获取沪深300指数成分和权重
# 
# 根据文档说明和用户要求：
# - 沪深300指数代码：000300.SZ  
# - 使用指定的交易日期：20250901

# %%
# 设置查询参数
trade_date = '20250901'  # 指定交易日期
index_code = '000300.SH'  # 沪深300指数代码 (修改为000300)

print(f"查询参数:")
print(f"指数代码: {index_code}")
print(f"交易日期: {trade_date}")

# %%
# 获取沪深300指数成分和权重
try:
    print(f"正在获取 {index_code} 指数成分和权重...")
    df = pro.index_weight(
        index_code=index_code,
        trade_date=trade_date
    )
    
    print(f"成功获取数据，共 {len(df)} 条记录")
    print("\n数据样例（前10条）:")
    print(df.head(10))
    
except Exception as e:
    print(f"获取数据失败: {e}")
    print("可能的原因:")
    print("1. 积分不足（需要至少2000积分）") 
    print("2. 网络连接问题")
    print("3. 参数错误")
    print("4. 指定日期无数据")

# %% [markdown]
# ## 3. 数据分析和处理
# 

# %%
# 数据基本信息
if 'df' in locals() and not df.empty:
    print("数据基本信息:")
    print(f"总记录数: {len(df)}")
    print(f"唯一成分股数量: {df['con_code'].nunique()}")
    print(f"交易日期范围: {df['trade_date'].min()} 到 {df['trade_date'].max()}")
    
    print("\n权重统计:")
    print(df['weight'].describe())
    
    # 显示数据结构
    print("\n数据结构:")
    print(df.dtypes)
    
    # 检查是否有重复数据
    duplicates = df.duplicated().sum()
    print(f"\n重复记录数: {duplicates}")


# %%
# 查看权重最高的前10只成分股
if 'df' in locals() and not df.empty:
    print("权重最高的前10只成分股:")
    
    # 获取最新交易日的数据
    latest_date = df['trade_date'].max()
    latest_df = df[df['trade_date'] == latest_date].copy()
    
    # 按权重排序
    top_stocks = latest_df.nlargest(10, 'weight')
    
    print(f"\n最新交易日 ({latest_date}) 权重排名:")
    for i, (_, row) in enumerate(top_stocks.iterrows(), 1):
        print(f"{i:2d}. {row['con_code']:10s} 权重: {row['weight']:6.4f}%")


# %% [markdown]
# ## 4. 数据保存
# 
# 将获取的数据保存到data目录下的CSV文件。

# %%
# 保存数据到文件
if 'df' in locals() and not df.empty:
    # 创建data目录（当前就在data目录下）
    data_dir = Path('.')
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存为CSV文件
    csv_filename = f"hs300_index_weight_{trade_date}.csv"
    csv_path = data_dir / csv_filename
    df.to_csv(csv_path, index=False, encoding='utf-8')
    
    # 提取con_code列表并保存为JSON文件
    # 按权重降序排列，确保顺序一致性
    df_sorted = df.sort_values('weight', ascending=False)
    con_code_list = df_sorted['con_code'].tolist()
    
    # 保存con_code列表为JSON文件
    json_filename = f"hs300_con_code_list_{trade_date}.json"
    json_path = data_dir / json_filename
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(con_code_list, f, ensure_ascii=False, indent=2)
    
    print(f"数据已保存:")
    print(f"CSV文件: {csv_path}")
    print(f"JSON文件: {json_path}")
    print(f"CSV文件大小: {csv_path.stat().st_size / 1024:.2f} KB")
    print(f"JSON文件大小: {json_path.stat().st_size / 1024:.2f} KB")
    print(f"保存记录数: {len(df)}")
    print(f"con_code数量: {len(con_code_list)}")
else:
    print("没有数据可保存")
