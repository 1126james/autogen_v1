from pathlib import Path
from typing import Dict, Any

def cleaning_reasoning_prompt(data_dict: Dict[str, Any], filepath: Path):
  return f"""<Data Cleaning Advisor>

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

<strict_rules>
    1. Use exact ACTUAL column names
    2. Only basic cleaning actions
    3. Clear, simple explanations
    4. Focus on practical solutions
    5. Do not ask any questions.
    6. NO EDA and NO visualizations.
</strict_rules>
"""