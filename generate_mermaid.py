"""
生成三个LangGraph图的mermaid文件
"""
import sys
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import dotenv
dotenv.load_dotenv()

from src.subgraphs.signal import build_signal_graph
from src.subgraphs.backtest import build_backtest_graph
from src.graph import create_main_graph


def generate_mermaid_files():
    """生成三个图的mermaid文件"""
    
    print("开始生成mermaid文件...\n")
    
    # 1. 生成signal子图的mermaid
    print("1. 生成signal子图...")
    try:
        signal_graph = build_signal_graph().compile()
        signal_mermaid = signal_graph.get_graph().draw_mermaid()
        
        signal_file = project_root / "signal_subgraph.mermaid"
        signal_file.write_text(signal_mermaid, encoding='utf-8')
        print(f"   ✅ 已生成: {signal_file}")
    except Exception as e:
        print(f"   ❌ 生成signal子图失败: {e}")
    
    # 2. 生成backtest子图的mermaid
    print("\n2. 生成backtest子图...")
    try:
        backtest_graph = build_backtest_graph().compile()
        backtest_mermaid = backtest_graph.get_graph().draw_mermaid()
        
        backtest_file = project_root / "backtest_subgraph.mermaid"
        backtest_file.write_text(backtest_mermaid, encoding='utf-8')
        print(f"   ✅ 已生成: {backtest_file}")
    except Exception as e:
        print(f"   ❌ 生成backtest子图失败: {e}")
    
    # 3. 生成main图的mermaid
    print("\n3. 生成main图...")
    try:
        main_graph = create_main_graph()
        main_mermaid = main_graph.get_graph().draw_mermaid()
        
        main_file = project_root / "main_graph.mermaid"
        main_file.write_text(main_mermaid, encoding='utf-8')
        print(f"   ✅ 已生成: {main_file}")
    except Exception as e:
        print(f"   ❌ 生成main图失败: {e}")
    
    print("\n全部完成！")


if __name__ == "__main__":
    generate_mermaid_files()
