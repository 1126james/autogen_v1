### BASIC TEMPLATE OF AUTOGEN !!! DO NOT EDIT!!!

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.agents._code_executor_agent import CodeExecutorAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_core import CancellationToken
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.models.openai import OpenAIChatCompletionClient
import asyncio
import math
from pathlib import Path
import venv

# Basic Configurations
model = "qwen2.5:14b"
model_url = "http://127.0.0.1:11434/v1"
api_key = "YOUR_API_KEY"
model_capabilities = {
                "vision": False,
                "function_calling": True,
                "json_output": False
            }

# Define Tools
async def calculator(expression: str) -> str:
    try:
        safe_dict = {
            'abs': abs,
            'round': round,
            'pi': math.pi,
            'e': math.e,
            'sqrt': math.sqrt,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'log': math.log,
            'log10': math.log10
        }
        
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        
        if isinstance(result, (int, float)):
            if result.is_integer():
                return str(int(result))
            return f"{result:.6f}".rstrip('0').rstrip('.')
        
        return str(result)
        
    except Exception as e:
        return f"Error: {str(e)}"

### Create Agents
# 1.
base_agent = AssistantAgent(
        name="base_agent",
        reflect_on_tool_use= True,
        model_client=OpenAIChatCompletionClient(
            model=model,
            base_url=model_url,
            api_key=api_key,
            model_capabilities=model_capabilities
        ),
        tools=[calculator],
        system_message="Use the appropriate tools to solve tasks. DONT force unnecessary tool usage. For coding task, ONLY EXPLICITLY provide the code WITHOUT executing."
    )

# 2.
code_executor = LocalCommandLineCodeExecutor(work_dir="coding")
code_executor = CodeExecutorAgent("code_executor", code_executor=code_executor,)

# 3.
code_checker = AssistantAgent(
        name="code_checker",
        reflect_on_tool_use= True,
        model_client=OpenAIChatCompletionClient(
            model=model,
            base_url=model_url,
            api_key=api_key,
            model_capabilities=model_capabilities
        ),
        system_message="Check whether the output matches the code. If yes, Reply with TERMINATE. If no, EXPLICITLY provide concise ordered suggestions on what needs to be fixed without providing any code."
    )

# Define workflow
async def main() -> None:
    # Define termination condition
    termination_approve = TextMentionTermination("TERMINATE")
    termination_max = MaxMessageTermination(max_messages=10)
    # 1. user message(str)
    # 2. FunctionCall(id, arg, name)
    # 3. FunctionExecutionResult(content, call_id) id==call_id
    # 4. result response
    termination = termination_approve | termination_max

    # Define a team
    agent_team = RoundRobinGroupChat(
        [base_agent, code_executor, code_checker], 
        termination_condition=termination
    )

    # Run the team and stream messages to the console
    stream = agent_team.run_stream(
        task="Write a python code to greet a user named James"
    )
    await Console(stream)

if __name__ == "__main__":
    asyncio.run(main())