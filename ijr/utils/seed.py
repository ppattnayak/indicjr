import random, os, numpy as np
def seed_all(s=42):
    random.seed(s); np.random.seed(s); os.environ["PYTHONHASHSEED"]=str(s)
