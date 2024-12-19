# Python lib
import asyncio
from pathlib import Path
import pandas as pd
from tqdm import tqdm
from typing import Dict, Any, Tuple
import venv

# Autogen-0.4
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.agents._code_executor_agent import CodeExecutorAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Local
from prompts import cleaning_reasoning_prompt, cleaning_coding_prompt, code_checking_prompt
from utils import CopyFile, LoadDataset, GetDatasetProfile, Spinner


# ONLY EDIT HERE
reasoning_model = "qwen2.5:32b-instruct-q8_0"
coding_model = "qwen2.5-coder:32b-instruct-q8_0"
llm_base_url = "http://34.204.63.234:11434/v1"
api_key = "none"
capabilities =  {
        "vision": False,
        "function_calling": False,
        "json_output": False
    }

# Reasoning Model Configuration
instruct_client_config = OpenAIChatCompletionClient(
    model=reasoning_model,
    base_url=llm_base_url,
    api_key=api_key,
    model_capabilities=capabilities
)

# Coding Model Configuration
code_client_config = OpenAIChatCompletionClient(
    model=coding_model,
    base_url=llm_base_url,
    api_key=api_key,
    model_capabilities=capabilities
)
# setup agents - cleaning team (1)
### 1.1 Cleaning reasoning agent
async def create_agents(filepath: Path) -> Tuple[AssistantAgent, AssistantAgent, CodeExecutorAgent, AssistantAgent]:
    with tqdm(total=4, 
             desc="Creating agents", 
             bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}',
             colour='green') as pbar:
        async def create_cleaning_reasoning_agent():
            cleaning_reasoning_agent = AssistantAgent(
                name="cleaning_reasoning_agent",
                model_client=instruct_client_config,
                # Somehow the first prompt would be overwritten by the initial task prompt (under run_cleaning_pipeline())
                # So this prompt has little to no impact
                system_message=f"""You are the first agent in the data cleaning pipeline."""
            )
            pbar.update(1)
            return cleaning_reasoning_agent

        ### 1.2 Cleaning code generator agent
        async def create_cleaning_coding_agent() -> AssistantAgent:
            cleaning_coding_agent = AssistantAgent(
                name="cleaning_coding_agent",
                model_client=code_client_config,
                # Testing XML format for consistent format.
                # Tested: plain text
                # To-test: md, json
                system_message=f"""
<DATA_CLEANING_CODE_GENERATOR>

<purpose>
    Generate data cleaning code based on data dictionary metadata.
</purpose>

<INPUT>
    FILE_PATH: {str(filepath)}
</INPUT>

<instructions>
    - Explicitly output necessary installation commands (sh) and cleaning code (python)
    - No analysis or insights included
    - Code only in two distinct blocks:
    1. sh command for library installation
    2. Python cleaning code
</instructions>

<REQUIREMENTS>
    1. Generate Python code to clean dataset using pandas or other NECESSARY lib
    2. Use EXACT column names and file paths
    3. Handle common data issues:
        - Missing values
        - Incorrect data types
        - Outliers
        - Inconsistent formats
        - Duplicates
</REQUIREMENTS>

<OUTPUT_FORMAT>
```sh
pip install
```
```python
# import necessary lib
import pandas as pd
# MUST IMPORT Path
from pathlib import Path

# Load actual dataset
df = pd.read_csv("{str(filepath)}")

# Cleaning operations here...


# Save cleaned dataset
output_path = Path("outputs/modified_{str(filepath.name)}")
# SAVE ACCORDING TO SPECIFIC FILE TYPE
df.to_csv(output_path, index=False)
print(f"Saved cleaned dataset to {{output_path}}")
```
</OUTPUT_FORMAT>

<STRICT_RULES>
    1. NO explanatory text or comments outside code blocks
    2. NO placeholder code - use actual column names
    3. NO data analysis or visualization code
    4. ONLY two code blocks: pip install and Python code
    5. MUST include final save operations
    6. Save using the CORRESPONDING file type
</STRICT_RULES>
""")
            pbar.update(1)
            return cleaning_coding_agent

        ### 2. Code executor
        # Setup working directory
        async def create_code_executor() -> CodeExecutorAgent:
            work_dir = Path("coding").absolute()
            work_dir.mkdir(exist_ok=True)
            print("")
            # Setup venv sheets and output directory
            sheets_dir = Path("coding/sheets").absolute()
            sheets_dir.mkdir(parents=True, exist_ok=True)
            outputs_dir = Path("coding/outputs").absolute()
            outputs_dir.mkdir(parents=True, exist_ok=True)


            # Define source and destination
            source_file = filepath.absolute()
            destination = sheets_dir / source_file.name  # Use the filename for destination

            # Copy the file from root to venv
            CopyFile(source_file, destination)
            tqdm.write(f"File successfully copied to {destination}")

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
            pbar.update(1)
            return CodeExecutorAgent("code_executor", code_executor=executor)

        ### 3. code checker agent
        async def create_code_checker() -> AssistantAgent:
            code_checker = AssistantAgent(
                name="code_checker",
                model_client=instruct_client_config,
                system_message=code_checking_prompt # To-do
            )
            pbar.update(1)
            return code_checker
        
        list_of_agents = await asyncio.gather(
            create_cleaning_reasoning_agent(), 
            create_cleaning_coding_agent(), 
            create_code_executor(), 
            create_code_checker()
        )
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
    try:
        # cleaning_reasoning, cleaning_coding, code_executor, code_checker
        cleaning_team = await create_agents(filepath=filepath)

        # Setup termination conditions
        text_term = TextMentionTermination("TERMINATE")
        len_term = MaxMessageTermination(12)
        termination = text_term | len_term

        # First phase: Data Cleaning
        cleaning_team_chat = RoundRobinGroupChat(
            cleaning_team,
            termination_condition=termination,
        )
        
        # Based on the provided json data dictionary, explicity generate the python code to clean it specifically. Dont use any fictional placeholder, use actual column names and file names.\nData dictionary:
        cleaning_task = f"""Data Cleaning Advisor

<purpose>
    Provide basic data cleaning recommendations for each column.
</purpose>

<data_dictionary>
    {data_dict}
</data_dictionary>

<dataset_location>
    {str(filepath)}
</dataset_location>

<instructions>
    - Review data dictionary
    - EXPLICITLY ONLY output SIMPLE data cleaning techniques the dataset with the hint provided by the data dictionary.
</instructions>

<output_format>
    For each column with issues:
    1. Column Name
    2. Issue Type
    3. Recommended Action
    4. Brief Reason
</output_format>

<rules>
    1. Use exact ACTUAL column names
    2. Only basic cleaning actions
    3. Clear, simple explanations
    4. Focus on practical solutions
    5. Do not ask any questions.
    6. NO EDA and NO visualizations.
</rules>
"""
    
        await Spinner.async_with_spinner(
            message="Loading: ",
            style="braille",
            console_class=Console,
            coroutine=cleaning_team_chat.run_stream(task=cleaning_task)
        )
    except Exception as e:
        raise Exception(f"An error occurred: {str(e)}")
        # Get cleaned dataframe and updated profile
        # cleaned_df = df  # This should be updated based on code_executor's output
        # cleaned_profile = GetDatasetProfile(cleaned_df)

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
    # First progress bar for data loading and profiling
    with tqdm(total=3,
              desc="Preparing dataset", 
              bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}',
              colour='green') as pbar:
        
        test_file = Path("sheets/sample.csv")
        pbar.update(1)
        
        df = LoadDataset(test_file)
        pbar.update(1)
        
        initial_profile = GetDatasetProfile(df)
        pbar.update(1)
    
    # Run the async operation (create_agents has its own progress bar)
    asyncio.run(run_cleaning_pipeline(df, initial_profile, test_file))
