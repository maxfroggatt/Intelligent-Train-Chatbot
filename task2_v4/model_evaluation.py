import pandas as pd
import matplotlib.pyplot as plt
from joblib import dump
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import KNeighborsRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# Load and clean CSV data
def load_data(path='all_services_with_features.csv'):
    df = pd.read_csv(path)
    return df.dropna().reset_index(drop=True)

# Split features and target variable
def split_features_target(df, target_col='y_delay_mins'):
    X = df.drop(columns=[target_col, 'rid', 'location'])
    y = df[target_col]
    bool_cols = X.select_dtypes(include='bool').columns
    X[bool_cols] = X[bool_cols].astype(int)
    return X.astype(float), y

# Train and evaluate models
def train_and_evaluate(X_train, X_test, y_train, y_test):
    results = {}

    # Define regression models
    estimators = {
        # 'LinearRegression': LinearRegression(),
        # 'KNN': KNeighborsRegressor(),
        'RandomForest': RandomForestRegressor(random_state=42),
        # 'ANN': MLPRegressor(
        #     hidden_layer_sizes=(100,),
        #     alpha=0.001,
        #     learning_rate_init=0.001,
        #     max_iter=1000,
        #     early_stopping=True,
        #     n_iter_no_change=10,
        #     validation_fraction=0.1
        # )
    }

    # Define hyperparameter grids for each model
    param_grids = {
        # 'LinearRegression': {},
        # 'KNN': {
        #     'model__n_neighbors': [3, 5, 7],
        #     'model__weights': ['uniform', 'distance']
        # },
        'RandomForest': {
            'model__n_estimators': [100, 200],
            'model__max_depth': [None, 10, 20]
        },
        # 'ANN': {
        #     'model__hidden_layer_sizes': [(50,), (100,)],
        #     'model__alpha': [1e-4, 1e-3],
        #     'model__learning_rate_init': [1e-3, 1e-4],
        #     'model__max_iter': [200, 500]
        # }
    }

    # Set up pipeline and grid search
    for name, estimator in estimators.items():
        pipe = Pipeline([
            ('scaler', StandardScaler()),
            ('model', estimator)
        ])
        grid = GridSearchCV(
            pipe,
            param_grids[name],
            cv=3,
            scoring='neg_mean_squared_error',
            n_jobs=-1,
            error_score='raise'
        )

        print(f"\nTraining {name}...")
        grid.fit(X_train, y_train)
        best_model = grid.best_estimator_
        preds = best_model.predict(X_test)

        # Save the best model pipeline
        model_filename = f'{name}_best_model.joblib'
        dump(best_model, model_filename)
        print(f"Saved {name} pipeline to {model_filename}")

        # Metrics
        mse = mean_squared_error(y_test, preds)
        mae = mean_absolute_error(y_test, preds)
        r2  = r2_score(y_test, preds)

        # Save best model results
        results[name] = {
            'best_params': grid.best_params_,
            'mse': mse,
            'mae': mae,
            'r2': r2
        }

        # Print results
        print(f"{name} best params: {grid.best_params_}")
        print(f"{name} Test MSE: {mse:.3f}")
        print(f"{name} Test MAE: {mae:.3f}")
        print(f"{name} Test R²:  {r2:.3f}")

        # Plot actual vs. predicted and save as PNG
        plt.figure(figsize=(6,6))
        plt.scatter(y_test, preds, alpha=0.3)
        plt.plot([y_test.min(), y_test.max()],
                 [y_test.min(), y_test.max()], 'r--', lw=2)
        plt.xlabel('Actual Delay (min)')
        plt.ylabel('Predicted Delay (min)')
        plt.title(f'{name}: Actual vs. Predicted')
        plt.tight_layout()
        png_filename = f'{name}_pred_vs_actual.png'
        plt.savefig(png_filename, format='png', dpi=300)
        plt.close()
        print(f"Saved plot to {png_filename}")
    return results

# Run training and evaluation
if __name__ == '__main__':
    df = load_data()
    X, y = split_features_target(df)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    results = train_and_evaluate(X_train, X_test, y_train, y_test)