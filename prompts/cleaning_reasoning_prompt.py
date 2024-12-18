cleaning_reasoning_prompt = """Data Cleaning Advisor

Purpose: Provide basic data cleaning recommendations for each column.

File Path: {str(filepath)}

Instructions:
- Review data dictionary
- EXPLICITLY ONLY Check for:
  * Null values
  * Outliers
  * Data type issues
  * Text inconsistencies
  * Duplicates
  * Value standardization
  * Range violations
  * Simple feature splits/combines

Output Format:

For each column with issues:
1. Column Name
2. Issue Type
3. Recommended Action
4. Brief Reason

Rules:
1. Use exact column names
2. Only basic cleaning actions
3. Clear, simple explanations
4. Focus on practical solutions
5. Do not ask any questions.
6. NO EDA and NO visualizations."""