"""AI LLM 服务模块 - 接口定义，待接入真实 API"""
from typing import List, Dict, AsyncIterator


class LLMService:
    """AI LLM 服务（预留接口）"""
    
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """非流式对话 - 待实现"""
        raise NotImplementedError("请接入 LLM API")
    
    async def chat_stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        """流式对话 - 待实现"""
        raise NotImplementedError("请接入 LLM API")


llm_service = LLMService()
