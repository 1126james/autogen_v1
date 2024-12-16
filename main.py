from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.agents._code_executor_agent import CodeExecutorAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import CancellationToken
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.models.openai import OpenAIChatCompletionClient
import asyncio
from pathlib import Path
import venv
from prompts import (
    cleaning_prompt,
    code_checking_prompt,
    transformation_prompt
)
import pandas as pd
from typing import Dict, Any

# Model Configuration
MODEL_CONFIG = {
    "model": "qwen2.5:14b",
    "base_url": "http://127.0.0.1:11434/v1",
    "api_key": "YOUR_API_KEY",
    "capabilities": {
        "vision": False,
        "function_calling": True,
        "json_output": False
    }
}

def create_model_client():
    return OpenAIChatCompletionClient(
        model=MODEL_CONFIG["model"],
        base_url=MODEL_CONFIG["base_url"],
        api_key=MODEL_CONFIG["api_key"],
        model_capabilities=MODEL_CONFIG["capabilities"]
    )

def setup_code_executor():
    work_dir = Path("coding").absolute()
    work_dir.mkdir(exist_ok=True)
    venv_dir = work_dir / ".venv"
    
    if not venv_dir.exists():
        venv_builder = venv.EnvBuilder(with_pip=True)
        venv_builder.create(venv_dir)
        venv_context = venv_builder.ensure_directories(venv_dir)
    else:
        venv_builder = venv.EnvBuilder(with_pip=True)
        venv_context = venv_builder.ensure_directories(venv_dir)
    
    executor = LocalCommandLineCodeExecutor(
        work_dir=str(work_dir),
        virtual_env_context=venv_context
    )
    return CodeExecutorAgent("code_executor", code_executor=executor)

def create_agents():
    model_client = create_model_client()
    
    cleaning_assistant = AssistantAgent(
        name="cleaning_assistant",
        reflect_on_tool_use=True,
        model_client=model_client,
        system_message=cleaning_prompt
    )
    
    transformation_assistant = AssistantAgent(
        name="transformation_assistant",
        reflect_on_tool_use=True,
        model_client=model_client,
        system_message=transformation_prompt
    )
    
    code_checker = AssistantAgent(
        name="code_checker",
        reflect_on_tool_use=True,
        model_client=model_client,
        system_message=code_checking_prompt
    )
    
    code_executor = setup_code_executor()
    
    return cleaning_assistant, transformation_assistant, code_executor, code_checker

async def run_cleaning_pipeline(df: pd.DataFrame, data_dict: Dict[str, Any]) -> pd.DataFrame:
    """
    Run the complete data cleaning and transformation pipeline
    """
    cleaning_assistant, transformation_assistant, code_executor, code_checker = create_agents()
    
    # Setup termination conditions
    termination = TextMentionTermination("TERMINATE")
    
    # First phase: Data Cleaning
    cleaning_team = RoundRobinGroupChat(
        [cleaning_assistant, code_executor, code_checker],
        termination_condition=termination
    )
    
    cleaning_task = f"Clean this dataset according to its profile:\n{data_dict}"
    await cleaning_team.run(task=cleaning_task)
    
    # Get cleaned dataframe and updated profile
    cleaned_df = df  # This should be updated based on code_executor's output
    cleaned_profile = get_dataset_profile(cleaned_df)
    
    # Second phase: Data Transformation
    transformation_team = RoundRobinGroupChat(
        [transformation_assistant, code_executor, code_checker],
        termination_condition=termination
    )
    
    transform_task = f"Suggest and apply transformations based on this profile:\n{cleaned_profile}"
    await transformation_team.run(task=transform_task)
    
    # Return the final processed dataframe
    return cleaned_df  # This should be the transformed version from code_executor

if __name__ == "__main__":
    # This section is for testing the pipeline directly
    from data_catalog import load_dataset, get_dataset_profile
    
    test_file = Path("sheets/sample.csv")
    df = load_dataset(test_file)
    initial_profile = get_dataset_profile(df)
    
    asyncio.run(run_cleaning_pipeline(df, initial_profile))
