"""
任务执行日志记录器

基于LangChain的BaseCallbackHandler机制，记录LLM和工具调用的完整信息
"""
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.agents import AgentAction, AgentFinish


class TaskLoggerCallbackHandler(BaseCallbackHandler):
    """任务执行日志记录器
    
    记录LangGraph执行过程中的所有LLM和工具调用信息到日志文件
    """
    
    def __init__(self, task_dir: Path):
        """初始化日志记录器
        
        Args:
            task_dir: 任务目录，日志文件将存储在此目录下
        """
        self.task_dir = Path(task_dir)
        self.task_dir.mkdir(parents=True, exist_ok=True)
        
        # 日志文件路径
        self.jsonl_log = self.task_dir / "execution_log.jsonl"
        self.text_log = self.task_dir / "execution_log.txt"
        
        # 当前节点名称（用于上下文追踪）
        self.current_node: Optional[str] = None
        
        # 初始化日志文件
        self._init_log_files()
    
    def _init_log_files(self):
        """初始化日志文件，写入头部信息"""
        timestamp = datetime.now().isoformat()
        
        # 写入文本日志头部
        with open(self.text_log, 'w', encoding='utf-8') as f:
            f.write(f"{'='*80}\n")
            f.write(f"LangGraph 执行日志\n")
            f.write(f"开始时间: {timestamp}\n")
            f.write(f"{'='*80}\n\n")
    
    def _write_jsonl(self, event_type: str, data: Dict[str, Any]):
        """写入JSON Lines格式的结构化日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "node_name": self.current_node,
            "data": data
        }
        
        with open(self.jsonl_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def _write_text(self, message: str):
        """写入人类可读的文本日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.text_log, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    
    def set_current_node(self, node_name: str):
        """设置当前执行的节点名称"""
        self.current_node = node_name
        self._write_text(f"\n{'='*80}")
        self._write_text(f"进入节点: {node_name}")
        self._write_text(f"{'='*80}")
        self._write_jsonl("node_start", {"node_name": node_name})
    
    def log_node_output(self, node_name: str, output: Dict[str, Any]):
        """记录节点输出"""
        # 过滤敏感或冗余信息
        filtered_output = {}
        for key, value in output.items():
            if key == 'messages':
                # 只记录消息数量
                filtered_output[key] = f"<{len(value)} messages>"
            elif key in ['execution_history', 'error_messages']:
                # 记录列表长度和最后一项
                if value:
                    filtered_output[key] = {
                        "count": len(value),
                        "latest": value[-1] if value else None
                    }
            else:
                filtered_output[key] = value
        
        self._write_jsonl("node_output", {
            "node_name": node_name,
            "output": filtered_output
        })
        
        # 文本日志记录关键信息
        if 'current_task' in output:
            self._write_text(f"  当前任务: {output['current_task']}")
        if 'execution_history' in output and output['execution_history']:
            self._write_text(f"  最新执行: {output['execution_history'][-1]}")
    
    # LLM回调方法
    def on_llm_start(
        self, 
        serialized: Dict[str, Any], 
        prompts: List[str], 
        **kwargs: Any
    ) -> None:
        """LLM开始调用时的回调"""
        self._write_text(f"\n[LLM] 开始调用")
        self._write_text(f"  模型: {serialized.get('name', 'unknown')}")
        
        # 记录提示词
        for i, prompt in enumerate(prompts):
            self._write_text(f"  提示词 [{i+1}]:")
            # 限制长度，避免日志过大
            prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt
            for line in prompt_preview.split('\n'):
                self._write_text(f"    {line}")
        
        self._write_jsonl("llm_start", {
            "model": serialized.get('name', 'unknown'),
            "prompts": prompts,
            "invocation_params": kwargs.get('invocation_params', {})
        })
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """LLM调用结束时的回调"""
        # 提取响应内容
        generations = response.generations[0] if response.generations else []
        output_text = generations[0].text if generations else ""
        
        self._write_text(f"[LLM] 调用结束")
        
        # 记录输出
        output_preview = output_text[:500] + "..." if len(output_text) > 500 else output_text
        self._write_text(f"  输出:")
        for line in output_preview.split('\n'):
            self._write_text(f"    {line}")
        
        # 记录token使用情况
        if response.llm_output and 'token_usage' in response.llm_output:
            token_usage = response.llm_output['token_usage']
            self._write_text(f"  Token使用: {token_usage}")
        
        self._write_jsonl("llm_end", {
            "output": output_text,
            "token_usage": response.llm_output.get('token_usage') if response.llm_output else None
        })
    
    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """LLM调用出错时的回调"""
        self._write_text(f"[LLM] 调用出错: {str(error)}")
        self._write_jsonl("llm_error", {"error": str(error)})
    
    # 工具回调方法
    def on_tool_start(
        self, 
        serialized: Dict[str, Any], 
        input_str: str, 
        **kwargs: Any
    ) -> None:
        """工具开始调用时的回调"""
        tool_name = serialized.get('name', 'unknown')
        self._write_text(f"\n[工具] 开始调用: {tool_name}")
        self._write_text(f"  输入: {input_str}")
        
        self._write_jsonl("tool_start", {
            "tool_name": tool_name,
            "input": input_str
        })
    
    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """工具调用结束时的回调"""
        self._write_text(f"[工具] 调用结束")
        
        # 限制输出长度
        output_preview = output[:500] + "..." if len(output) > 500 else output
        self._write_text(f"  输出: {output_preview}")
        
        self._write_jsonl("tool_end", {"output": output})
    
    def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        """工具调用出错时的回调"""
        self._write_text(f"[工具] 调用出错: {str(error)}")
        self._write_jsonl("tool_error", {"error": str(error)})
    
    # Agent回调方法
    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> None:
        """Agent执行动作时的回调"""
        self._write_text(f"\n[Agent] 决策动作: {action.tool}")
        self._write_text(f"  工具输入: {action.tool_input}")
        if action.log:
            log_preview = action.log[:300] + "..." if len(action.log) > 300 else action.log
            self._write_text(f"  推理日志: {log_preview}")
        
        self._write_jsonl("agent_action", {
            "tool": action.tool,
            "tool_input": action.tool_input,
            "log": action.log
        })
    
    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> None:
        """Agent完成时的回调"""
        self._write_text(f"\n[Agent] 执行完成")
        self._write_text(f"  返回值: {finish.return_values}")
        
        self._write_jsonl("agent_finish", {
            "return_values": finish.return_values,
            "log": finish.log
        })
    
    # Chain回调方法
    def on_chain_start(
        self, 
        serialized: Dict[str, Any], 
        inputs: Dict[str, Any], 
        **kwargs: Any
    ) -> None:
        """Chain开始执行时的回调"""
        chain_name = serialized.get('name', 'unknown')
        self._write_text(f"\n[Chain] 开始执行: {chain_name}")
        
        self._write_jsonl("chain_start", {
            "chain_name": chain_name,
            "inputs_keys": list(inputs.keys())
        })
    
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Chain执行结束时的回调"""
        self._write_text(f"[Chain] 执行结束")
        
        self._write_jsonl("chain_end", {
            "outputs_keys": list(outputs.keys())
        })
    
    def on_chain_error(self, error: Exception, **kwargs: Any) -> None:
        """Chain执行出错时的回调"""
        self._write_text(f"[Chain] 执行出错: {str(error)}")
        self._write_jsonl("chain_error", {"error": str(error)})
    
    def write_summary(self, final_state: Optional[Dict[str, Any]] = None):
        """写入执行摘要"""
        summary_path = self.task_dir / "summary.json"
        
        summary = {
            "end_time": datetime.now().isoformat(),
            "log_files": {
                "jsonl": str(self.jsonl_log),
                "text": str(self.text_log)
            }
        }
        
        if final_state:
            # 提取关键状态信息
            summary["final_state"] = {
                "data_ready": final_state.get('data_ready', False),
                "indicators_ready": final_state.get('indicators_ready', False),
                "signal_ready": final_state.get('signal_ready', False),
                "backtest_completed": final_state.get('backtest_completed', False),
                "execution_steps": len(final_state.get('execution_history', [])),
                "error_count": len(final_state.get('error_messages', []))
            }
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        # 写入文本日志尾部
        self._write_text(f"\n{'='*80}")
        self._write_text(f"执行完成")
        self._write_text(f"摘要文件: {summary_path}")
        self._write_text(f"{'='*80}\n")
