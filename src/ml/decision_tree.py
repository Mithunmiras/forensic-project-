import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder
from sklearn.compose import ColumnTransformer

from sklearn.tree import DecisionTreeRegressor

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

# =====================================================
# STEP 1: Load Dataset
# =====================================================

df = pd.read_csv("data/processed/superstore_cleaned.csv")

print("Shape:", df.shape)

print("\nColumns:")
print(df.columns.tolist())

print("\nFirst 5 Rows:")
print(df.head())

# =====================================================
# STEP 2: Select Features and Target
# =====================================================

X = df[
    [
        "category",
        "sub_category",
        "quantity",
        "discount",
        "shipping_cost",
        "shipping_days",
        "market",
        "order_priority",
        "year",
        "weeknum",
    ]
]

y = df["sales"]

print("\nFeature Shape:", X.shape)
print("Target Shape:", y.shape)

# =====================================================
# STEP 3: Encode Categorical Columns
# =====================================================

categorical_features = [
    "category",
    "sub_category",
    "market",
    "order_priority",
]

preprocessor = ColumnTransformer(
    transformers=[
        (
            "cat",
            OrdinalEncoder(
                handle_unknown="use_encoded_value",
                unknown_value=-1
            ),
            categorical_features,
        )
    ],
    remainder="passthrough",
)

X_encoded = preprocessor.fit_transform(X)
print(type(X_encoded))
print(X_encoded.shape)
print(preprocessor.get_feature_names_out())
print("\nEncoded Feature Shape:", X_encoded.shape)

# =====================================================
# STEP 4: Train-Test Split
# =====================================================

X_train, X_test, y_train, y_test = train_test_split(
    X_encoded,
    y,
    test_size=0.20,
    random_state=42,
)

print("\nTraining Feature Shape:", X_train.shape)
print("Testing Feature Shape:", X_test.shape)

# =====================================================
# STEP 5: Train Decision Tree
# =====================================================

model = DecisionTreeRegressor(
    random_state=42,
    max_depth=10
)

model.fit(X_train, y_train)

print("\n✅ Decision Tree Model Trained Successfully!")

# =====================================================
# STEP 6: Prediction
# =====================================================

predictions = model.predict(X_test)

print("\nFirst 10 Predictions:")
print(predictions[:10])

# =====================================================
# STEP 7: Evaluation
# =====================================================

mae = mean_absolute_error(y_test, predictions)
mse = mean_squared_error(y_test, predictions)
rmse = np.sqrt(mse)
r2 = r2_score(y_test, predictions)

print("\n================ MODEL PERFORMANCE ================")
print(f"MAE  : {mae:.2f}")
print(f"MSE  : {mse:.2f}")
print(f"RMSE : {rmse:.2f}")
print(f"R²   : {r2:.4f}")
print("===================================================")