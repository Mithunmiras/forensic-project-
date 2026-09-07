import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.preprocessing import OneHotEncoder
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_squared_error
from sklearn.metrics import r2_score
# Database Connection
engine = create_engine(
    "postgresql://postgres:yogesh123@localhost:5432/retailiq_db"
)

# Load Data
query = "SELECT * FROM superstore;"
df = pd.read_sql(query, engine)

print("Shape:", df.shape)
print("\nColumns:")
print(df.columns.tolist())

print("\nFirst 5 Rows:")
print(df.head())
# Select Features (X) and Target (y)

features = [
    "category",
    "sub_category",
    "segment",
    "market",
    "quantity",
    "discount",
    "shipping_cost",
    "shipping_days",
    "year",
    "weeknum"
]

X = df[features]
y = df["sales"]

print("Feature Shape:", X.shape)
print("Target Shape:", y.shape)

print("\nSelected Features:")
print(X.head())

print("\nTarget:")
print(y.head())
# Categorical columns
categorical_columns = [
    "category",
    "sub_category",
    "segment",
    "market"
]

# Apply One-Hot Encoding
X = pd.get_dummies(
    X,
    columns=categorical_columns,
    drop_first=True
)

print("\nEncoded Feature Shape:", X.shape)

print("\nEncoded Features:")
print(X.head())
# Split the dataset

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)

print("\nTraining Feature Shape:", X_train.shape)
print("Testing Feature Shape:", X_test.shape)

print("\nTraining Target Shape:", y_train.shape)
print("Testing Target Shape:", y_test.shape)

# Create the Linear Regression model
model = LinearRegression()

# Train the model
model.fit(X_train, y_train)

print("✅ Model trained successfully!")
# Predict sales for the test data
predictions = model.predict(X_test)

print("\nFirst 10 Predicted Sales:")
print(predictions[:10])
# Calculate Mean Absolute Error
mae = mean_absolute_error(y_test, predictions)

print("\nMean Absolute Error (MAE):", mae)
#rsme
mse = mean_squared_error(y_test, predictions)
rmse = np.sqrt(mse)

print("\nMean Squared Error (MSE):", mse)
print("Root Mean Squared Error (RMSE):", rmse)
# Calculate R² Score
r2 = r2_score(y_test, predictions)

print("\nR² Score:", r2)