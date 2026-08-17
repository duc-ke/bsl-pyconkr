from fastapi import Request

from app.services.meals import MealService


def get_meal_service(request: Request) -> MealService:
    return request.app.state.meal_service
