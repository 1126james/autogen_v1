from autogen_agentchat.agents import AssistantAgent, CodeExecutorAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
import asyncio
import math
import pandas as pd
from prompts import *

# Basic Configurations
model = "qwen2.5:7b-instruct-q4_0"
model_url = "http://127.0.0.1:11434/v1"
api_key = "YOUR_API_KEY"
model_capabilities = {
                "vision": False,
                "function_calling": False,
                "json_output": False
            }



# Create Agents
cleaning_agent = AssistantAgent(
        name="cleaning_agent",
        model_client=OpenAIChatCompletionClient(
            model=model,
            base_url=model_url,
            api_key=api_key,
            model_capabilities=model_capabilities
        ),
        system_message=cleaning_prompt
    )

execute_agent = CodeExecutorAgent(
    name= 'execute_agent',

)

# Define workflow
async def main() -> None:
    # Define termination condition
    termination_approve = TextMentionTermination("TERMINATE")
    termination_max = MaxMessageTermination(max_messages=5)
    # 1. user message(str)
    # 2. FunctionCall(id, arg, name)
    # 3. FunctionExecutionResult(content, call_id) id==call_id
    # 4. result response
    termination = termination_approve | termination_max

    # Define a team
    agent_team = RoundRobinGroupChat(
        [math_agent], 
        termination_condition=termination
    )

    # Run the team and stream messages to the console
    stream = agent_team.run_stream(
        task="I have earned 1k$, I need to share it with 3 of my friends. how much would each of us have if we want to buy a 50$ cake?"
    )
    await Console(stream)

if __name__ == "__main__":
    asyncio.run(main())