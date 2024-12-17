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
from pathlib import Path
from copy_file import copy_file
import venv
# from prompts.cleaning_prompt import cleaning_prompt
# from prompts.transformation_prompt import transformation_prompt
# from prompts.code_checking_prompt import code_checking_prompt
import pandas as pd
from typing import Dict, Any

# ONLY EDIT HERE
# Model Configuration
model_config = {
    "model": "qwen2.5:72b-instruct-q4_k_m",
    "base_url": "http://34.204.63.234:11434/v1",
    "api_key": "YOUR_API_KEY",
    "capabilities": {
        "vision": False,
        "function_calling": False,
        "json_output": False
    }
}


client_config = OpenAIChatCompletionClient(
    model=model_config["model"],
    base_url=model_config["base_url"],
    api_key=model_config["api_key"],
    model_capabilities=model_config["capabilities"]
)
# setup agents - cleaning team (1)
### 1. Cleaning code generator agent
cleaning_agent = AssistantAgent(
    name="cleaning_agent",
    model_client=client_config, 
    system_message="""
<|im_start|>system
<identity>You are a data cleaning specialist focusing on data quality and integrity.</identity>

<context>
You will analyze a data dictionary containing dataset metadata (column types, null counts, unique values, etc.) and generate optimized cleaning code.
You must preserve data integrity and handle edge cases appropriately.
</context>

<input_format>
Data dictionary structure:
{
    "dataset_info": {
        "total_rows": int,
        "total_columns": int,
        "duplicate_rows": int
    },
    "columns": {
        "column_name": {
            "dtype": str,
            "null_count": int,
            "unique_count": int,
            "sample_values": list
        }
    }
}
</input_format>

<output_format>
Provide exactly THREE blocks in this order:

1. SINGLE shell command block with ALL required libraries:
```shell
pip install lib1 lib2 lib3
```

2. SINGLE Python code block with ALL cleaning code:
```python
# All your code here including:
# - imports
# - data loading
# - cleaning functions
# - main execution
# - error handling
# - validation
```

3. SINGLE explanation block with bullet points:
- What issues were addressed
- Why specific approaches were chosen
- Performance considerations
</output_format>

<rules>
1. Reference exact file paths and column names
2. Generate memory-efficient code
3. Include data validation
4. Handle errors gracefully
5. Add code comments
6. Combine ALL code in respective single blocks
7. No mixing or splitting of code blocks
</rules>

<best_practices>
- Use pandas efficient methods
- Process data in chunks if needed
- Validate data types
- Log cleaning steps
- Include error handling
</best_practices>
<|im_end|>
"""
) # To-do, refine prompt

### 2. Code executor
# Setup working directory
async def create_code_executor(filepath: Path) -> CodeExecutorAgent:
    work_dir = Path("coding").absolute()
    work_dir.mkdir(exist_ok=True)

    # Setup venv sheets directory
    sheets_dir = Path("coding/sheets").absolute()
    sheets_dir.mkdir(parents=True, exist_ok=True)

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
code_checker = AssistantAgent(
    name="code_checker",
    model_client=client_config,
    system_message="""
<|im_start|>system
<identity>You are a senior code quality analyst specializing in data processing, with expertise in pandas, numpy, and Python performance optimization.</identity>

<review_criteria>
1. FUNCTIONALITY
   - Correct data transformations
   - Requirements fulfillment
   - Data integrity preservation
   - Type consistency

2. PERFORMANCE
   - Memory efficiency
   - Processing speed
   - Resource utilization
   - Scalability concerns

3. CODE QUALITY
   - Pandas/Numpy best practices
   - Vectorization usage
   - Memory management
   - Code readability

4. ERROR HANDLING
   - Edge cases coverage
   - Data validation
   - Error recovery
   - Exception handling
</review_criteria>

<severity_definitions>
CRITICAL: Issues that...
- Cause incorrect results
- Lead to runtime errors
- Break data integrity
- Violate core requirements
- Create security vulnerabilities

OPTIONAL: Suggestions for...
- Performance optimization
- Code maintainability
- Resource efficiency
- Better practices
- Enhanced robustness

PERFECT: Code that...
- Meets all requirements
- Uses optimal approaches
- Follows best practices
- Handles all edge cases
</severity_definitions>

<output_template>
ONE of the following formats only:

### Critical Issues Found:
CRITICAL:
- [Specific issue with direct impact]
- [Specific issue with direct impact]
*FIX THE CODE*

### Improvements Possible:
OPTIONAL:
- [Specific improvement with benefit]
- [Specific improvement with benefit]
*TERMINATE*

### Optimal Implementation:
PERFECT:
- [Evidence-based explanation of optimality]
*TERMINATE*
</output_template>

<rules>
STRICT REQUIREMENTS:
1. Choose exactly ONE response category
2. Never mix categories
3. Never provide code snippets
4. Link each issue to specific impact
5. Focus on data processing context
6. Provide actionable feedback only
7. Reference specific functions/methods
8. Consider scalability implications
</rules>
<|im_end|>
""" # To-do
)


# transformation_assistant = AssistantAgent(
#     name="transformation_assistant",
#     model_client=client_config,
#     system_message=transformation_prompt # To-do
# )

async def run_cleaning_pipeline(df: pd.DataFrame, data_dict: Dict[str, Any], filepath: Path) -> pd.DataFrame:
    """
    Run the complete data cleaning and transformation pipeline
    """
    code_executor = await create_code_executor(filepath=filepath)

    cleaning_team = [cleaning_agent, code_executor, code_checker]
    
    # Setup termination conditions
    text_term = TextMentionTermination("TERMINATE")
    len_term = MaxMessageTermination(9)
    termination = text_term | len_term
    
    # First phase: Data Cleaning
    cleaning_team = RoundRobinGroupChat(
        cleaning_team,
        termination_condition=termination
    )
    # Based on the provided json data dictionary, explicity generate the python code to clean it specifically. Dont use any fictional placeholder, use actual column names and file names.\nData dictionary:
    cleaning_task = f"\n\n# Data Dictionary:\n\n{data_dict}\n\n## Dataset Location:\n\n{str(filepath)}"
    await Console(cleaning_team.run_stream(task=cleaning_task))
    
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
