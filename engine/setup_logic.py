"""
Tynd wrapper omkring data/cars.py — holder app.py fri for at kende til
databasens interne struktur.
"""
from data.cars import (
    list_classes, list_cars, get_car_params, params_as_text, coverage_report,
    validate_setup_changes,
)

__all__ = ["list_classes", "list_cars", "get_car_params", "params_as_text",
           "coverage_report", "validate_setup_changes"]
