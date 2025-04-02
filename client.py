import asyncio
from mcp import ClientSession
from contextlib import AsyncExitStack

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv() #加载  .env文件

class MCPClient:
    def __init__(self):
        """初始化mcp客户端"""
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("BASE_URL")
        self.model = os.getenv("MODELa")

        if not self.openai_api_key:
            raise ValueError("未找到apikey")

        self.client = OpenAI(api_key=self.openai_api_key,base_url=self.base_url)

    
    async def process_query(self,query:str) -> str:
        """调用openai api"""
        messages = [{"role":"system","content":"永远用中文回答"},
                    {"role":"user","content":query}]
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model = self.model,
                    messages=messages,
                    temperature=0.7,
                    stream=True,
                )
            )
            # return response.choices[0].message.content
        
            for chunk in response:
                if chunk.choices[0].delta.content: 
                    text = chunk.choices[0].delta.content # 只打印实际的文本内容
                    print(text, end="", flush=True)

        except Exception as e:
            return f"错误:{str(e)}"
        

    async def connect_to_mock_server(self):
        """模拟mcp服务器的连接"""
        print("MCP客户端已初始化,但未连接到服务器")

    async def chat_loop(self):
        """运行交互式聊天循环"""
        print("\nMCP 客户端已启动。输入'quit'退出")

        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == 'quit':
                    break

                await self.process_query(query)

                # response = await self.process_query(query)
                # print(f"\n AI:{response}")

            except Exception as e:
                print(f"\n发生错误: {str(e)}")

    async def cleanup(self):
        """清理资源"""
        await self.exit_stack.aclose()



async def main():
    client = MCPClient()
    try:
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())