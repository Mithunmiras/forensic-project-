import joblib
import pandas as pd

# Load trained model
model = joblib.load("models/random_forest_sales_model.pkl")

# Load preprocessor
preprocessor = joblib.load("models/random_forest_preprocessor.pkl")


def predict_sales(data):

    # Convert dictionary into DataFrame
    df = pd.DataFrame([data])

    # Apply the same preprocessing used during training
    X = preprocessor.transform(df)

    # Predict sales
    prediction = model.predict(X)

    # Return a normal Python float
    return float(prediction[0])