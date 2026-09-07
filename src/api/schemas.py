
from pydantic import BaseModel


class SalesPredictionRequest(BaseModel):

    category: str

    sub_category: str

    quantity: int

    discount: float

    shipping_cost: float

    shipping_days: int

    market: str

    order_priority: str

    year: int

    weeknum: int

    month: int

    quarter: int

    day_of_week: int