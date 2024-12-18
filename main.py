from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.agents._code_executor_agent import CodeExecutorAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.models.openai import OpenAIChatCompletionClient
import asyncio
from pathlib import Path
from copy_file import copy_file
import venv
from prompts import cleaning_reasoning_prompt, cleaning_coding_prompt, code_checking_prompt
import pandas as pd
from typing import Dict, Any, Tuple


# ONLY EDIT HERE
# Reasoning Model Configuration
instruct_model_config = {
    "model": "qwen2.5:32b-instruct-q8_0",
    "base_url": "http://34.204.63.234:11434/v1",
    "api_key": "YOUR_API_KEY",
    "capabilities": {
        "vision": False,
        "function_calling": False,
        "json_output": False
    }
}

instruct_client_config = OpenAIChatCompletionClient(
    model=instruct_model_config["model"],
    base_url=instruct_model_config["base_url"],
    api_key=instruct_model_config["api_key"],
    model_capabilities=instruct_model_config["capabilities"]
)

# Coding Model Configuration
code_model_config = {
    "model": "qwen2.5-coder:32b-instruct-q8_0",
    "base_url": "http://34.204.63.234:11434/v1",
    "api_key": "YOUR_API_KEY",
    "capabilities": {
        "vision": False,
        "function_calling": False,
        "json_output": False
    }
}

code_client_config = OpenAIChatCompletionClient(
    model=code_model_config["model"],
    base_url=code_model_config["base_url"],
    api_key=code_model_config["api_key"],
    model_capabilities=code_model_config["capabilities"]
)
# setup agents - cleaning team (1)
### 1.1 Cleaning reasoning agent
async def create_agents(filepath: Path) -> Tuple[AssistantAgent, AssistantAgent, CodeExecutorAgent, AssistantAgent]:
    async def create_cleaning_reasoning_agent():
        cleaning_reasoning_agent = AssistantAgent(
            name="cleaning_agent",
            model_client=instruct_client_config, 
            system_message=f"""You are the first agent in the data cleaning pipeline.""" # To-do
        ) # To-do, refine prompt
        return cleaning_reasoning_agent

    ### 1.2 Cleaning code generator agent
    async def create_cleaning_coding_agent() -> AssistantAgent:
        cleaning_coding_agent = AssistantAgent(
            name="cleaning_coding_agent",
            model_client=code_client_config,
            system_message=f"""
Data Cleaning Code Generator

Purpose: Generate data cleaning code based on data dictionary metadata.

Dataset Location: {str(filepath)}

Instructions:
- Explicitly output necessary installation commands (sh) and cleaning code (python)
- No analysis or insights included
- Code only in two distinct blocks:
  1. sh command for library installation
  2. Python cleaning code

Requirements:
- Use exact file paths and column names
- Python code only
- Keep 2 code blocks separated
- Correct code block format

Output Format:
```sh
pip install lib1 lib2 lib3
```
```python
# Your python code line 1
# Your python code line 2
```

Rules:
1. Reference exact paths/columns
2. Sh and Python code only
3. Only 2 blocks in response (1 for sh, 1 for py)
4. At the end, use the head() function to display top 5 rows in terminal.
5. At the end, save the modified dataset to 'modified_'+ {str(filepath.name)} under the directory 'outputs/'
""")
        return cleaning_coding_agent

    ### 2. Code executor
    # Setup working directory
    async def create_code_executor() -> CodeExecutorAgent:
        work_dir = Path("coding").absolute()
        work_dir.mkdir(exist_ok=True)

        # Setup venv sheets and output directory
        sheets_dir = Path("coding/sheets").absolute()
        sheets_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir = Path("coding/outputs").absolute()
        outputs_dir.mkdir(parents=True, exist_ok=True)
        

        # Define source and destination
        source_file = filepath.absolute()
        destination = sheets_dir / source_file.name  # Use the filename for destination

        # Copy the file from root to venv
        copy_file(source_file, destination)

        # Setup venv for code executor
        venv_dir = work_dir / ".venv"
        venv_builder = venv.EnvBuilder(with_pip=True)
        if not venv_dir.exists():
            venv_builder.create(venv_dir)
        venv_context = venv_builder.ensure_directories(venv_dir)

        executor = LocalCommandLineCodeExecutor(
            work_dir=str(work_dir),
            virtual_env_context=venv_context
        )
        return CodeExecutorAgent("code_executor", code_executor=executor)

    ### 3. code checker agent
    async def create_code_checker() -> AssistantAgent:
        code_checker = AssistantAgent(
            name="code_checker",
            model_client=instruct_client_config,
            system_message=code_checking_prompt # To-do
        )
        return code_checker
    
    list_of_agents = await asyncio.gather(create_cleaning_reasoning_agent(), create_cleaning_coding_agent(), create_code_executor(), create_code_checker())
    return list_of_agents


# transformation_assistant = AssistantAgent(
#     name="transformation_assistant",
#     model_client=instruct_client_config,
#     system_message=transformation_prompt # To-do
# )

async def run_cleaning_pipeline(df: pd.DataFrame, data_dict: Dict[str, Any], filepath: Path) -> pd.DataFrame:
    """
    Run the complete data cleaning and transformation pipeline
    """
    
    # cleaning_reasoning, cleaning_coding, code_executor, code_checker
    cleaning_team = await create_agents(filepath=filepath)
    
    # Setup termination conditions
    text_term = TextMentionTermination("TERMINATE")
    len_term = MaxMessageTermination(12)
    termination = text_term | len_term
    
    # First phase: Data Cleaning
    cleaning_team_chat = RoundRobinGroupChat(
        cleaning_team,
        termination_condition=termination
    )
    # Based on the provided json data dictionary, explicity generate the python code to clean it specifically. Dont use any fictional placeholder, use actual column names and file names.\nData dictionary:
    cleaning_task = f"""Data Cleaning Advisor

Purpose: Provide basic data cleaning recommendations for each column.

<Data Dictionary>
{data_dict}
</Data Dictionary>

Dataset Location: {str(filepath)}

Instructions:
- Review data dictionary
- EXPLICITLY ONLY output SIMPLE data cleaning techniques the dataset with the hint provided by the data dictionary.

Output Format:

For each column with issues:
1. Column Name
2. Issue Type
3. Recommended Action
4. Brief Reason

Rules:
1. Use exact ACTUAL column names
2. Only basic cleaning actions
3. Clear, simple explanations
4. Focus on practical solutions
5. Do not ask any questions.
6. NO EDA and NO visualizations.
"""
    
    await Console(cleaning_team_chat.run_stream(task=cleaning_task))
    
    # Get cleaned dataframe and updated profile
    # cleaned_df = df  # This should be updated based on code_executor's output
    # cleaned_profile = get_dataset_profile(cleaned_df)
    
    # # Second phase: Data Transformation
    # transformation_team = RoundRobinGroupChat(
    #     [transformation_assistant, code_executor, code_checker],
    #     termination_condition=termination
    # )
    
    # transform_task = f"Suggest and apply transformations based on this profile:\n{cleaned_profile}"
    # await Console(transformation_team.run_stream(task=transform_task))
    
    # # Return the final processed dataframe
    # return cleaned_df  # This should be the transformed version from code_executor

if __name__ == "__main__":
    # This section is for testing the pipeline directly
    from data_catalog import load_dataset, get_dataset_profile
    
    test_file = Path("sheets/sample.csv")
    df = load_dataset(test_file)
    initial_profile = get_dataset_profile(df)
    
    asyncio.run(run_cleaning_pipeline(df, initial_profile, test_file))
