import asyncio
from mcp import ClientSession
from contextlib import AsyncExitStack
from typing import Optional
import json

import os
from openai import OpenAI
from dotenv import load_dotenv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv() #加载  .env文件

class MCPClient:
    def __init__(self):
        """初始化mcp客户端"""
        self.session: Optional[ClientSession]= None
        self.exit_stack = AsyncExitStack()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("BASE_URL")
        self.model = os.getenv("MODELa")

        if not self.openai_api_key:
            raise ValueError("未找到apikey")

        self.client = OpenAI(api_key=self.openai_api_key,base_url=self.base_url)


    async def connect_to_server(self, server_script_path: str):
        """连接到MCP服务器并列出可用工具"""
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not(is_python or is_js):
            raise ValueError("服务器脚本必须是.py或者.js文件")
        
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        #启动mcp服务器建立通信
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio,self.write))
        await self.session.initialize()

        #列出MCP服务器上的工具
        response = await self.session.list_tools()
        tools = response.tools
        print("\n已连接到服务器,支持以下工具:",[tool.name for tool in tools])

    
    async def process_query(self, query:str) -> str:
        """调用openai api，支持流式输出"""
        messages = [{"role":"user","content":query}]
        
        response = await self.session.list_tools()

        available_tools = [{
            "type":"function",
            "function":{
                "name":tool.name,
                "description":tool.description,
                "input_schema":tool.inputSchema
            }
        } for tool in response.tools]
        print(available_tools)

        collected_messages = []
        first_stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=available_tools,
            stream=True
        )

        tool_calls = []
        full_message = {}
        
        # 收集第一次流式输出的内容
        for chunk in first_stream:
            if chunk.choices[0].delta.tool_calls:
                # 收集工具调用信息
                if len(tool_calls) == 0:
                    tool_calls.append(chunk.choices[0].delta.tool_calls[0])
                else:
                    if chunk.choices[0].delta.tool_calls[0].function.arguments:
                        tool_calls[0].function.arguments += chunk.choices[0].delta.tool_calls[0].function.arguments
            elif chunk.choices[0].delta.content:
                # 正常的文本内容
                print(chunk.choices[0].delta.content, end="", flush=True)
                collected_messages.append(chunk.choices[0].delta.content)

        # 如果有工具调用
        if tool_calls:
            tool_call = tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            # 调用工具
            result = await self.session.call_tool(tool_name, tool_args)
            print(f"\n\n[Calling tool {tool_name} with args {tool_args}]\n\n")

            # 构建包含工具调用结果的新消息
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tool_call.id,
                    "function": {"name": tool_name, "arguments": json.dumps(tool_args)},
                    "type": "function"
                }]
            })
            messages.append({
                "role": "tool",
                "content": result.content[0].text,
                "tool_call_id": tool_call.id
            })

            # 第二次流式输出
            print("\nAI: ", end="", flush=True)
            second_stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )
            
            collected_messages = []  # 重置收集的消息
            for chunk in second_stream:
                if chunk.choices[0].delta.content:
                    print(chunk.choices[0].delta.content, end="", flush=True)
                    collected_messages.append(chunk.choices[0].delta.content)
            print()
        
        return "".join(collected_messages)


    async def chat_loop(self):
        """运行交互式聊天循环"""
        print("\nMCP 客户端已启动。输入'quit'退出")

        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == 'quit':
                    break

                print("\nAI: ", end="", flush=True)  # 在开始流式输出前打印提示
                response = await self.process_query(query)

            except Exception as e:
                print(f"\n发生错误: {str(e)}")

    async def cleanup(self):
        """清理资源"""
        await self.exit_stack.aclose()



async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    import sys
    asyncio.run(main())