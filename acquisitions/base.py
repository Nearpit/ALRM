import torch
import numpy as np

class Acquisition: 
    latent = None

    def __init__(self, 
                 clf,
                 pool,
                 random_seed,
                 budget):
        self.clf = clf       
        self.pool = pool
        self.random_seed = random_seed
        self.budget = budget

    def get_scores(self):
        pass

    def query(self):
        all_scores = self.get_scores()
        max_scores = np.argwhere(all_scores == all_scores.max()).ravel()
        self.pool.set_seed()
        idx = np.random.choice(max_scores, 1)[0]
        return self.pool.idx_ulb[idx]
    