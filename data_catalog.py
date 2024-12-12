import pandas as pd

def load_csv(csv_path):
    """
    Load CSV data into a pandas DataFrame.
    """
    df = pd.read_csv(csv_path)
    print("CSV loaded successfully.")
    return df

def get_column_details(df):
    """
    Extract schema details from the DataFrame.
    Returns a dictionary with column details.
    """
    details = {}
    for col in df.columns:
        details[col] = {
            'dtype': str(df[col].dtype),
            'unique_values': df[col].nunique(),
            'sample_values': df[col].dropna().unique()[:5].tolist()
        }
    return details

df = load_csv('sheets/sample.csv')
details = get_column_details(df)
print(details)