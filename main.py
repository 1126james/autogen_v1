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
from prompts import coding_assistant_prompt, code_checking_prompt

### Basic Configurations
# Configure our base model
model = "qwen2.5:14b"
model_url = "http://127.0.0.1:11434/v1"
api_key = "YOUR_API_KEY"
model_capabilities = {
                "vision": False,
                "function_calling": True,
                "json_output": False
            }

# Config the client on top of the base model
model_client = OpenAIChatCompletionClient(
            model=model,
            base_url=model_url,
            api_key=api_key,
            model_capabilities=model_capabilities
        )

### Create Agents
# 1. coding_assistant
coding_assistant = AssistantAgent(
    name="coding_assistant",
    reflect_on_tool_use= True,
    model_client=model_client,
    system_message=coding_assistant_prompt)

# 2. code_executor_agent
work_dir = Path("coding").absolute()
work_dir.mkdir(exist_ok=True)
venv_dir = str(work_dir / ".venv")
venv_builder = venv.EnvBuilder(with_pip=True)
if not Path(venv_dir).exists():
    venv_builder.create(venv_dir)
venv_context = venv_builder.ensure_directories(venv_dir)
code_executor = LocalCommandLineCodeExecutor(
    work_dir=work_dir,  # Use string path instead of Path object
    virtual_env_context=venv_context
)
code_executor_agent = CodeExecutorAgent("code_executor", code_executor=code_executor)

# 3.code_checker
code_checker = AssistantAgent(
        name="code_checker",
        reflect_on_tool_use= True,
        model_client=model_client,
        system_message=code_checking_prompt)

# Define workflow
async def main() -> None:
    # List of agents
    agents = [coding_assistant, code_executor_agent, code_checker]
    # Define termination condition
    termination_approve = TextMentionTermination("TERMINATE")
    termination_max = MaxMessageTermination(max_messages=len(agents)*3)
    # 1. user message(str)
    # 2. FunctionCall(id, arg, name)
    # 3. FunctionExecutionResult(content, call_id) id==call_id
    # 4. result response
    termination = termination_approve | termination_max

    # Define a team
    agent_team = RoundRobinGroupChat(
        agents, 
        termination_condition=termination_approve
    )

    # Run the team and stream messages to the console
    stream = agent_team.run_stream(
        task="draw me a smiley face"
    )
    await Console(stream)

if __name__ == "__main__":
    asyncio.run(main())