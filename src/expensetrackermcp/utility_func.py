import json
from datetime import datetime
from importlib.resources import files

CATEGORIES_FILE = files(
    "expensetrackermcp.resources"
).joinpath("categories.json")

def validate_date(date_value):
    try:
        return datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError:
        return None

def validate_category_filters(category, subcategory, categories):

    if category and category not in categories:
        return {
            "status": "error",
            "message": f"Invalid category: {category}"
        }

    if subcategory and category:
        if subcategory not in categories[category]:
            return {
                "status": "error",
                "message": f"Invalid subcategory '{subcategory}' for category '{category}'."
            }

    if subcategory and not category:
        valid_subcategory = any(
            subcategory in subcategories
            for subcategories in categories.values()
        )

        if not valid_subcategory:
            return {
                "status": "error",
                "message": f"Invalid subcategory: {subcategory}"
            }

    return None

def validate_filter_inputs(start_date, end_date, category, subcategory):

    # Check whether at least one filter is provided
    if all(value is None for value in [
        start_date, end_date, category, subcategory
    ]):
        return {
            "status": "error",
            "message": "Please provide at least one filter."
        }

    # Validate start date
    start_date_obj = None
    if start_date:
        start_date_obj = validate_date(start_date)

        if start_date_obj is None:
            return {
                "status": "error",
                "message": "Invalid start date. Expected YYYY-MM-DD."
            }

    # Validate end date
    end_date_obj = None
    if end_date:
        end_date_obj = validate_date(end_date)

        if end_date_obj is None:
            return {
                "status": "error",
                "message": "Invalid end date. Expected YYYY-MM-DD."
            }

    # Validate date range
    if start_date_obj and end_date_obj:
        if start_date_obj > end_date_obj:
            return {
                "status": "error",
                "message": "Start date cannot be after end date."
            }

    # Validate categories
    categories = load_categories()

    category_error = validate_category_filters(
        category, subcategory, categories
    )

    if category_error:
        return category_error

    return None

def validate_update_fields(date, amount, category, subcategory, note):
    updates = {
        "date": date,
        "amount": amount,
        "category": category,
        "subcategory": subcategory,
        "note": note
    }

    updates = {
        key: value
        for key, value in updates.items()
        if value is not None
    }

    if not updates:
        return None, {
            "status": "error",
            "message": "Please provide at least one field to update."
        }

    if ("category" in updates) != ("subcategory" in updates):
        return None, {
            "status": "error",
            "message": "Category and subcategory must be updated together."
        }

    if "date" in updates:
        if validate_date(updates["date"]) is None:
            return None, {
                "status": "error",
                "message": "Invalid date. Expected YYYY-MM-DD."
            }

    if "category" in updates:
        categories = load_categories()

        category_error = validate_category_filters(
            updates["category"],
            updates["subcategory"],
            categories
        )

        if category_error:
            return None, category_error

    if "amount" in updates:
        if not isinstance(updates["amount"], (int, float)) or isinstance(updates["amount"], bool):
            return None, {
                "status": "error",
                "message": "Amount must be a number."
            }

        if updates["amount"] <= 0:
            return None, {
                "status": "error",
                "message": "Amount must be greater than zero."
            }

    if "note" in updates and not isinstance(updates["note"], str):
        return None, {
            "status": "error",
            "message": "Note must be a string."
        }

    return updates, None

def load_categories():
    with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
