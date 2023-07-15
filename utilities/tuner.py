import optuna
from torch.utils.data import DataLoader, Subset

import utilities

class BaseClass:
    all_hypers = {"lr", "weight_decay", "layers_size"}

    def __init__(self, pool, model, tunable_hypers):
        self.pool = pool
        self.model = model
        self.tunable_hypers = tunable_hypers
        self.general_tuning = self.all_hypers == self.tunable_hypers

    def add_input_output_size(self, layers_size):
        layers_size.insert(0, self.pool.n_features)
        layers_size.append(self.pool.n_classes)
        return layers_size
    
class Tuner(BaseClass):
                                              # How many fold it warms up
    pruner_configs = {"n_startup_trials": 5, "n_warmup_steps": 500}
    study_configs = {"pruner": optuna.pruners.MedianPruner(**pruner_configs)}

    #CAVEAT check the objective direction   #DEBUG  
    def __init__(self, n_trials, direction="minimize", *args, **kwargs):    
        super().__init__(*args, **kwargs)
        # optuna.logging.set_verbosity(optuna.logging.WARNING) #DEBUG
        self.n_trials = n_trials  
        self.study_configs["direction"] = direction
        self.study_configs["sampler"] = optuna.samplers.TPESampler(seed=self.pool.split_seed)


    def __call__(self):
        study = optuna.create_study(**self.study_configs)
        study.optimize(Objective(model=self.model, pool=self.pool, tunable_hypers=self.tunable_hypers), n_trials=self.n_trials)
        return self.align_params(study.best_params)
    
    
    def align_params(self, best_params):
        decoded_params = {
            "lr": best_params["lr"],
            "weight_decay": best_params["weight_decay"]
        }

        if "layers_size" in best_params:
            decoded_params["layers_size"] = best_params["layers_size"]
        else:
            width_dict = {k: v for k, v in best_params.items() if "width_" in k}
            layers_size = []
            for idx, _ in enumerate(width_dict.keys()):
                layers_size.append(width_dict[f"width_{idx}"])
            if self.model.model_arch_name  == "AE":
                # TODO check whether it works correctly
                layers_size.extend(layers_size[1::-1])
            
            decoded_params["layers_size"] = self.add_input_output_size(layers_size)

        return decoded_params

class Objective(BaseClass):
    ranges = {
        "weight_decay": {"low": 1e-7, "high":1e-1, "log":True},
        "depth": {"low": 1, "high":4},
        "width": {"low": 2, "high": 96},
        "lr": {"low": 1e-6, "high":1e-1}
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "MLP" in self.model.model_arch_name:
            self.define_func = self.define_MLP
        elif "AE" in self.model.model_arch_name:
            self.define_func = self.define_AE


    def __call__(self, trial):
        suggest_dict = self.suggest_params(trial)
        self.model.update_model_configs(suggest_dict)
        val_loss = utilities.OnlineAvg()
        if self.general_tuning:
            for fold_num, (train_ds, val_ds) in enumerate(self.pool.train_val_kfold):
                self.pool.set_seed(self.pool.split_seed)
                train_loader =  DataLoader(Subset(self.pool.train_val_dataset, train_ds), 
                                            batch_size=self.pool.batch_size, 
                                            shuffle=True)
                self.pool.set_seed(self.pool.split_seed)
                val_loader =  DataLoader(Subset(self.pool.train_val_dataset, val_ds), 
                                        batch_size=self.pool.batch_size,
                                        drop_last=False)
                train_perf, val_perf = self.model.fit(train_loader=train_loader, val_loader=val_loader)
                val_loss += float(val_perf[0])
                print(fold_num, suggest_dict, val_perf)
        else:
            train_perf, val_perf = self.model.fit(train_loader=self.pool.train_loader, val_loader=self.pool.val_loader)
            val_loss = val_perf[0]
        return val_loss


    def suggest_params(self, trial):
        suggest_dict = {}
        for key in self.all_hypers:
            if key in self.tunable_hypers:
                if key == "layers_size":
                    suggest_dict[key] = self.add_input_output_size(self.define_func(trial))
                elif key in ["weight_decay", "lr"]:
                    suggest_dict[key] = trial.suggest_float(key, **self.ranges[key])
                else:
                    raise Exception("Something is wrong with the tuning process")
            else:
                suggest_dict[key] = trial.suggest_categorical(key, [self.model.model_configs[key]]) # the given hyper
        return suggest_dict
    
    def define_MLP(self, trial):
        layers_size = []
        depth = trial.suggest_int("depth", **self.ranges["depth"])
        for idx in range(depth):
            layers_size.append(trial.suggest_int(f"width_{idx}", **self.ranges["width"]))

        return layers_size

    # def define_AE(self, trial):
    #     current_width = trial.suggest_int("width_0", **self.params_ranges["width"])
    #     bottleneck =  trial.suggest_int("bottleneck", self.params_ranges["width"]["low"], current_width - 1) # -1 to exclude upper bound
    #     layers_size = [current_width, bottleneck, current_width]

    #     current_width = trial.suggest_int(f"width_{1}", bottleneck, current_width - 1) # -1 to exclude upper bound
    #     i = 2

    #     while current_width > bottleneck:
    #         layers_size.insert(i, current_width)
    #         layers_size.insert(-i, current_width)
    #         current_width = trial.suggest_int(f"width_{i}", bottleneck, current_width - 1) # -1 to exclude upper bound
    #         i += 1

    #     return layers_size
   
