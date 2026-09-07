from fastapi import APIRouter

from src.api.schemas import SalesPredictionRequest
from src.api.predictor import predict_sales


router = APIRouter()


@router.post("/predict")
def predict(request: SalesPredictionRequest):

    # Convert Pydantic object to dictionary
    data = request.dict()

    # Get prediction
    result = predict_sales(data)

    return {
        "predicted_sales": result
    }