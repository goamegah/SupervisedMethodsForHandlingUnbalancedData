import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from sklearn.model_selection import train_test_split, StratifiedKFold
from src.core.Processing import Processing
from src.core.Model import Model
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from src.core.globals import PARAMS_GRID


class ComputeModel:

    def __init__(
            self,
            df_X: pd.DataFrame,
            y: pd.Series,
            model_name: str,
            process: Processing,
            hyperparameters: dict = None,
            l_order: list = None,
            positive_mod=None,
            grid_search=False,
            random_search=False,
            stratify=True,
            params_grid=None,
            cv=3,
            verbose=1
    ):
        self.df_X = df_X
        self.y = y
        self.search = grid_search or random_search
        self.stratify = stratify
        if not self.search:
            self.model = Model(model_name, hyperparameters=hyperparameters)
        else:
            self.params_grid = PARAMS_GRID[model_name] if params_grid is None else params_grid
            cv = cv if not stratify else StratifiedKFold(cv)
            if random_search:
                search = RandomizedSearchCV(Model(model_name).model, param_distributions=self.params_grid, cv=cv,
                                            verbose=verbose)
            else:
                search = GridSearchCV(Model(model_name).model, self.params_grid, verbose=verbose, cv=cv)
            self.model = Model(model_name, search=search)
        self.process = process
        self.l_order = l_order
        modalities_y = pd.unique(self.y)
        if positive_mod is None:
            positive_mod = modalities_y[0]
        if not (positive_mod in modalities_y):
            raise Exception(f"{positive_mod} should be modality of {y}")
        self.positive_mod = positive_mod

    def numerize(self, df: pd.DataFrame) -> dict:
        if self.l_order is not None:
            result = self.process.df_to_numerical(df, l_order=self.l_order)
            df = result["df_transform"]
            mapping = result["mapping"]
            return {"df_transform": df, "mapping": mapping}
        else:
            df = self.process.df_to_numerical(df, l_order=self.l_order)["df_transform"]
            return {"df_transform": df}

    def split(self, test_size=.2, random_state=42) -> None:
        df_to_np = self.numerize(self.df_X)
        X = np.array(df_to_np["df_transform"])
        mapping = df_to_np["mapping"] if "mapping" in df_to_np.keys() else None
        y = np.array(self.y == self.positive_mod).reshape(-1)
        stratify = y if self.stratify else None
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=random_state,
                                                            stratify=stratify)
        if self.l_order:
            self.dict_split = {
                "arrays": {
                    "X_train": X_train,
                    "y_train": y_train.reshape(-1),
                    "X_test": X_test,
                    "y_test": y_test.reshape(-1)
                },
                "columns_features": df_to_np["df_transform"].columns,
                "mapping": mapping
            }
        else:
            self.dict_split = \
                {
                    "arrays": {
                        "X_train": X_train,
                        "y_train": y_train.reshape(-1),
                        "X_test": X_test,
                        "y_test": y_test.reshape(-1)
                    },
                    "columns_features": df_to_np["df_transform"].columns
                }

    def fit(self, test_size=.2, random_state=42) -> None:
        self.split(test_size, random_state)
        X_train = self.dict_split["arrays"]["X_train"]
        y_train = self.dict_split["arrays"]["y_train"]
        if not self.search:
            self.model.fit(X_train, y_train)
        else:
            self.model.search.fit(X_train, y_train)
            self.model.update()

    def metrics(self, plot_roc=False, ax: Axes = None):
        X, y = self.dict_split["arrays"]["X_test"], self.dict_split["arrays"]["y_test"]
        return self.model.metrics(X, y.reshape(-1), plot_roc=plot_roc, ax=ax)

    def predict_proba(self, df: pd.DataFrame):
        return self.model.predict_proba(np.array(self.numerize(df)["df_transform"]))

    def permutation_importance_model(self, scoring="roc_auc"):
        return self.model.permutation_importance_model(
            self.dict_split["arrays"]["X_train"],
            self.dict_split["arrays"]["y_train"],
            scoring
        )
