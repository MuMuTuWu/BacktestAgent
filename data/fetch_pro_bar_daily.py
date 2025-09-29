# %% [markdown]
# # HS300 日线行情下载（pro_bar）
# 使用 Tushare `pro_bar` 接口并行拉取沪深300成分股的日线后复权行情，并将结果保存为 Parquet。

# %%
import os
import warnings
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep

import pandas as pd
import tushare as ts
import dotenv
from tqdm.auto import tqdm


# %%
warnings.filterwarnings("ignore", category=FutureWarning, module="tushare")

dotenv.load_dotenv()

def _clean_env(value: str | None, key: str) -> str:
    if value is None:
        raise ValueError(f"环境变量 {key} 未配置")
    cleaned = value.strip()
    if cleaned and cleaned[0] == cleaned[-1] and cleaned[0] in (chr(39), chr(34)):
        cleaned = cleaned[1:-1]
    return cleaned

tushare_token = _clean_env(os.getenv('TUSHARE_TOKEN'), 'TUSHARE_TOKEN')
start_date = _clean_env(os.getenv('START_DATE'), 'START_DATE')
end_date = _clean_env(os.getenv('END_DATE'), 'END_DATE')

ts.set_token(tushare_token)
codes_path = Path('hs300_con_code_list_20250901.json')  # 脚本在data目录下运行，直接使用文件名
if not codes_path.exists():
    raise FileNotFoundError(f'未找到 constituents 文件: {codes_path}')

with open(codes_path, 'r', encoding='utf-8') as f:
    ts_codes = json.load(f)
ts_codes = sorted(ts_codes)
print(f'共加载 {len(ts_codes)} 支沪深300成分股。')


# %%
sleep_interval = 0.35  # 控制API调用速率，200次/分钟限制
max_workers = 8

def fetch_pro_bar(code: str):
    try:
        df = ts.pro_bar(
            ts_code=code,
            start_date=start_date,
            end_date=end_date,
            asset='E',
            adj='hfq',
            freq='D',
        )
        if df is None or df.empty:
            return None
        df['source_ts_code'] = code
        return df
    finally:
        sleep(sleep_interval)

output_dir = Path(f'{start_date}-{end_date}')  # 脚本在data目录下运行，直接创建子目录
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'hs300_pro_bar_daily.parquet'
backup_path = output_dir / 'hs300_pro_bar_daily.csv'

existing_df: pd.DataFrame | None = None
existing_codes: set[str] = set()
if output_path.exists():
    try:
        existing_df = pd.read_parquet(output_path)
        if 'ts_code' in existing_df.columns:
            existing_df['ts_code'] = existing_df['ts_code'].astype(str)
            existing_codes = set(existing_df['ts_code'].dropna().unique())
        else:
            print('现有 parquet 文件缺失 ts_code 字段，将视为无历史数据。')
            existing_df = None
    except Exception as exc:
        print(f'读取历史 parquet 失败，将重新拉取全量数据：{exc}')
        existing_df = None

missing_codes = [code for code in ts_codes if code not in existing_codes]

if existing_df is not None:
    print(
        f'历史数据覆盖 {len(existing_codes)} 支股票。'
        f"{'已完整覆盖成分股。' if not missing_codes else '存在缺失，将补全后再保存。'}"
    )
else:
    print('未找到历史 parquet 文件，将拉取全量数据。')

codes_to_fetch = ts_codes if existing_df is None else missing_codes

if codes_to_fetch:
    print(f'准备下载 {len(codes_to_fetch)} 支股票的数据。')

    results: list[pd.DataFrame] = []
    errors: dict[str, str] = {}
    progress = tqdm(total=len(codes_to_fetch), desc='下载进度', unit='股票')

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_pro_bar, code): code for code in codes_to_fetch}
        for future in as_completed(futures):
            code = futures[future]
            df = None
            try:
                df = future.result()
            except Exception as exc:  # 捕获单个任务异常
                errors[code] = str(exc)
            if df is not None:
                results.append(df)
            progress.update(1)

    progress.close()

    print(f'成功拉取 {len(results)} 支股票的数据。失败 {len(errors)} 支。')
    if errors:
        for symbol, message in list(errors.items())[:10]:
            print(f"{symbol}: {message}")
else:
    results = []
    print('历史数据已覆盖所有成分股，本次无需下载。')

frames: list[pd.DataFrame] = []
if existing_df is not None and not existing_df.empty:
    frames.append(existing_df)
if results:
    downloaded = pd.concat(results, axis=0, ignore_index=True)
    frames.append(downloaded)

if frames:
    combined = pd.concat(frames, axis=0, ignore_index=True)
    combined.sort_values(['ts_code', 'trade_date'], inplace=True)
    combined.drop_duplicates(subset=['ts_code', 'trade_date'], keep='last', inplace=True)
else:
    combined = pd.DataFrame()

if combined.empty:
    print('未获取到任何数据，未生成文件。')
else:
    combined.to_parquet(output_path, index=False)
    combined.to_csv(backup_path, index=False)
    print(f'输出 {len(combined)} 条记录至 {output_path}')
    print(f'备份 CSV 已保存至 {backup_path}')
