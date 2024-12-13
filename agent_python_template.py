import venv
from pathlib import Path
import asyncio
from autogen_core import CancellationToken
from autogen_agentchat.messages import TextMessage
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_agentchat.agents._code_executor_agent import CodeExecutorAgent

task = TextMessage(content="Here is some code ```python\nprint('Hello world')```",source="agent")

async def run_code_executor_agent() -> None:
    # Create a code executor agent that uses a venv container to execute code.
    code_executor = LocalCommandLineCodeExecutor(work_dir="coding")
    code_executor_agent = CodeExecutorAgent("code_executor", code_executor=code_executor)
    # Run the agent with a given code snippet.
    response = await code_executor_agent.on_messages([task], CancellationToken())
    print(response.chat_message.content)


asyncio.run(run_code_executor_agent())