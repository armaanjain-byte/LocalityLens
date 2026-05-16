import pandas as pd
from pprint import pprint

df = pd.read_parquet("data/raw/train-00000-of-00012.parquet")

sample = df.iloc[0]

print("\nCOLUMNS:")
print(df.columns)

print("\nINSTANCE:")
print(sample["instance_id"])

print("\nTRAJECTORY TYPE:")
print(type(sample["trajectory"]))

print("\nTRAJECTORY LENGTH:")
print(len(sample["trajectory"]))

print("\nFIRST STEP:")
pprint(sample["trajectory"][0])

print("\nSECOND STEP:")
pprint(sample["trajectory"][1])