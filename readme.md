# Usage
1. pip install -r requirements.txt
2. use virtual env please
3. make sure you have a /sheets/sample.csv
3. python main.py

## BUG
I have set the below termination condition, but sometimes the agents would infinitely loop, just ctrl+c to escape.

text_term = TextMentionTermination("TERMINATE")
len_term = MaxMessageTermination(9)
termination = text_term | len_term