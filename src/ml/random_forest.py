import os
import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OrdinalEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

# =====================================================
# STEP 1 : LOAD DATASET
# =====================================================

df = pd.read_csv("data/processed/superstore_cleaned.csv")

print("=" * 60)
print("DATASET INFORMATION")
print("=" * 60)

print("Original Shape:", df.shape)

# =====================================================
# STEP 2 : CONVERT DATE COLUMN
# =====================================================

df["order_date"] = pd.to_datetime(
    df["order_date"],
    errors="coerce"
)

# Remove invalid dates if any
df = df.dropna(subset=["order_date"])

# =====================================================
# STEP 3 : DATE FEATURE ENGINEERING
# =====================================================

df["month"] = df["order_date"].dt.month

df["quarter"] = df["order_date"].dt.quarter

df["day_of_week"] = df["order_date"].dt.dayofweek

print("\nAfter Feature Engineering Shape:")
print(df.shape)

print("\nNew Columns Added:")
print([
    "month",
    "quarter",
    "day_of_week"
])

# =====================================================
# STEP 4 : SELECT FEATURES
# =====================================================

features = [

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

    "month",

    "quarter",

    "day_of_week"

]

X = df[features]

y = df["sales"]

print("\nFeature Shape:")
print(X.shape)

print("Target Shape:")
print(y.shape)

# =====================================================
# STEP 5 : ENCODE CATEGORICAL FEATURES
# =====================================================

categorical_features = [

    "category",

    "sub_category",

    "market",

    "order_priority"

]

preprocessor = ColumnTransformer(

    transformers=[

        (

            "cat",

            OrdinalEncoder(

                handle_unknown="use_encoded_value",

                unknown_value=-1

            ),

            categorical_features

        )

    ],

    remainder="passthrough"

)

X_encoded = preprocessor.fit_transform(X)

print("\nEncoded Feature Shape:")
print(X_encoded.shape)

# =====================================================
# STEP 6 : TRAIN TEST SPLIT
# =====================================================

X_train, X_test, y_train, y_test = train_test_split(

    X_encoded,

    y,

    test_size=0.20,

    random_state=42

)

print("\nTraining Feature Shape:")
print(X_train.shape)

print("Testing Feature Shape:")
print(X_test.shape)

# =====================================================
# STEP 7 : RANDOM FOREST MODEL
# =====================================================

model = RandomForestRegressor(

    n_estimators=500,

    max_depth=15,

    min_samples_split=10,

    min_samples_leaf=10,

    max_features=0.5,

    random_state=42,

    n_jobs=-1

)

model.fit(X_train, y_train)

print("\n✅ Random Forest Model Trained Successfully!")

# =====================================================
# STEP 8 : PREDICTION
# =====================================================

predictions = model.predict(X_test)

print("\nFirst 10 Predictions:")
print(predictions[:10])

# =====================================================
# STEP 9 : EVALUATION
# =====================================================

mae = mean_absolute_error(
    y_test,
    predictions
)

mse = mean_squared_error(
    y_test,
    predictions
)

rmse = np.sqrt(mse)

r2 = r2_score(
    y_test,
    predictions
)

print("\n" + "=" * 60)
print("MODEL PERFORMANCE")
print("=" * 60)

print(f"MAE  : {mae:.2f}")
print(f"MSE  : {mse:.2f}")
print(f"RMSE : {rmse:.2f}")
print(f"R²   : {r2:.4f}")

# =====================================================
# STEP 10 : FEATURE IMPORTANCE
# =====================================================

importance = pd.DataFrame({

    "Feature": features,

    "Importance": model.feature_importances_

})

importance = importance.sort_values(

    by="Importance",

    ascending=False

)

print("\n" + "=" * 60)
print("FEATURE IMPORTANCE")
print("=" * 60)

print(importance)

print("\nTop 10 Features")

print(importance.head(10))

# =====================================================
# STEP 11 : SAVE MODEL
# =====================================================

os.makedirs(

    "models",

    exist_ok=True

)

joblib.dump(

    model,

    "models/random_forest_sales_model.pkl"

)

joblib.dump(

    preprocessor,

    "models/random_forest_preprocessor.pkl"

)

print("\n✅ Model Saved Successfully!")

print("models/random_forest_sales_model.pkl")

print("models/random_forest_preprocessor.pkl")