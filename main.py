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
from prompts import cleaning_reasoning_prompt, cleaning_checking_prompt
from utils import CopyFile, LoadDataset, GetDatasetProfile, Spinner

# Only edit here AND filepath under if __name__ == "__main__":
reasoning_model = "qwen2.5:32b-instruct-q8_0"
coding_model = "qwen2.5-coder:32b-instruct-q8_0"

# Common config
llm_base_url = "http://34.204.63.234:11434/v1"
api_key = "none"
capabilities =  {
        "vision": False,
        "function_calling": False,
        "json_output": False
    }

#######################################################################
#   !!! DONT EDIT BELOW EXCEPT FOR if __name__ == "__main__":   !!!   #
#######################################################################

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

### setup agents - cleaning reasoning team 1/4
async def create_cleaning_reasoning_agents(filepath: Path) -> Tuple[AssistantAgent, AssistantAgent]:
    
    # tqdm progress bar
    with tqdm(total=3,
             desc="Creating cleaning reasoning team agents",
             bar_format='{desc:>30}{postfix: <1} {bar}|{n_fmt:>4}/{total_fmt:<4}',
             colour='green') as pbar:
        
        async def _create_Data_Cleaning_Planner() -> AssistantAgent:
            Data_Cleaning_Planner = AssistantAgent(
                name="Data_Cleaning_Planner",
                model_client=instruct_client_config,
                system_message=cleaning_reasoning_prompt(filepath),
            )
            pbar.update(1)
            return Data_Cleaning_Planner
        
        async def _create_Plan_Validation_Assistant() -> AssistantAgent:
            Plan_Validation_Assistant = AssistantAgent(
                name="Plan_Validation_Assistant",
                model_client=instruct_client_config,
                system_message=cleaning_checking_prompt(filepath),
            )
            pbar.update(1)
            return Plan_Validation_Assistant
        
        list_of_cleaning_reasoning_agents = await asyncio.gather(
            _create_Data_Cleaning_Planner(),
            _create_Plan_Validation_Assistant(),
        )
        pbar.update(1)
        return list_of_cleaning_reasoning_agents
    
### setup agents - cleaning coding team 2/4
async def create_cleaning_reasoning_agents(filepath: Path) -> Tuple[AssistantAgent, CodeExecutorAgent, AssistantAgent]:
    # tqdm progress bar
    with tqdm(total=3,
             desc="Creating cleaning coding team agents",
             bar_format='{desc:>30}{postfix: <1} {bar}|{n_fmt:>4}/{total_fmt:<4}',
             colour='green') as pbar:
        
        async def _create_cleaning_coding_agent() -> AssistantAgent:
            cleaning_coding_agent = AssistantAgent(
                name="cleaning_coding_agent",
                model_client=code_client_config,
                system_message=cleaning_coding_prompt(filepath))
            pbar.update(1)
            return cleaning_coding_agent

        async def _create_code_executor() -> CodeExecutorAgent:
            # Setup working directory
            work_dir = Path("coding").absolute()
            work_dir.mkdir(exist_ok=True)
            sheets_dir = Path("coding/sheets").absolute()   # Setup venv .sheets/ directory
            sheets_dir.mkdir(parents=True, exist_ok=True)
            outputs_dir = Path("coding/outputs").absolute() # Setup venv .output/ directory
            outputs_dir.mkdir(parents=True, exist_ok=True)

            # Copy uploaded file to venv
            source_file = filepath.absolute()               # Define source and destination
            destination = sheets_dir / source_file.name     # Use the filename for destination
            CopyFile(source_file, destination)
            tqdm.write(f"File successfully copied to {destination}")

            # Setup venv for code executor
            venv_dir = work_dir / ".venv"
            venv_builder = venv.EnvBuilder(with_pip=True)
            if not venv_dir.exists():
                venv_builder.create(venv_dir)
            venv_context = venv_builder.ensure_directories(venv_dir)

            # Final config on code executor class
            executor = LocalCommandLineCodeExecutor(
                work_dir=str(work_dir),
                virtual_env_context=venv_context
            )
            pbar.update(1)
            return CodeExecutorAgent("code_executor", code_executor=executor)

        ### 1.4 code checker agent
        async def _create_code_checker() -> AssistantAgent:
            code_checker = AssistantAgent(
                name="code_checker",
                model_client=instruct_client_config,
                system_message=code_checking_prompt(filepath) # To-do
            )
            pbar.update(1)
            return code_checker

        list_of_cleaning_agents = await asyncio.gather(
            _create_cleaning_coding_agent(),
            _create_code_executor(),
            _create_code_checker()
        )
        return list_of_cleaning_coding_agents


# transformation_assistant = AssistantAgent(
#     name="transformation_assistant",
#     model_client=instruct_client_config,
#     system_message=transformation_prompt # To-do
# )

async def cleaning_reasoning_pipeline(data_dict: Dict[str, Any], filepath: Path):
    """
    Run the complete data cleaning and transformation pipeline
    """
    try:
        # cleaning_reasoning_agent, 
        cleaning_reasoning_team = await create_cleaning_reasoning_agents(filepath)
        # cleaning_team = [cleaning_team[0], cleaning_team[1]]
        
        # Setup termination conditions
        statusu_pass = TextMentionTermination("Overall Status: Pass")
        max_round = MaxMessageTermination(5)
        termination = statusu_pass | max_round

        # First phase: Data Cleaning (Reasoning)
        cleaning_team_chat = RoundRobinGroupChat(
            cleaning_team,
            termination_condition=termination,
        )
        
        # A loading spinner to know if the code is frozen or not
        await Spinner.async_with_spinner(
            message="Loading: ",
            style="braille",
            console_class=Console,
            coroutine=cleaning_team_chat.run_stream(task=cleaning_reasoning_prompt(filepath, data_dict), cancellation_token=None)
        )
        # Uncomment below to run the code without spinner
        # from autogen_agentchat.ui import Console
        # await cleaning_team_chat.run_stream(task=cleaning_reasoning_prompt(filepath, data_dict), cancellation_token=None)
        
    except Exception as e:
        raise Exception(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    with tqdm(total=3,
              desc="Preparing dataset",
              bar_format='{desc:>30}{postfix: <1} {bar}|{n_fmt:>4}/{total_fmt:<4}',
              colour='green') as pbar:
        # Edit file path
        test_file = Path("sheets/credit_card_transactions.csv")
        pbar.update(1)
        df = LoadDataset(test_file)
        pbar.update(1)
        # Custom function in utils/ to get data dict in markdown/natural language/json format
        # so far with qwen models, json format is the most consistent for dataset comprehension
        initial_profile = GetDatasetProfile(df, output_format="json")
        pbar.update(1)

    asyncio.run(cleaning_reasoning_pipeline(initial_profile, test_file))
