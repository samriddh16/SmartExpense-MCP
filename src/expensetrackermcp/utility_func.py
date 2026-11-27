import json
import statistics
from collections import defaultdict
from datetime import datetime
from importlib.resources import files
from expensetrackermcp.database import engine
from sqlalchemy import text

CATEGORIES_FILE = files(
    "expensetrackermcp.resources"
).joinpath("categories.json")

def validate_date(date_value):
    try:
        return datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError:
        return None

def validate_date_range(start_date=None, end_date=None):
    start_date_obj = None
    end_date_obj = None

    if start_date:
        start_date_obj = validate_date(start_date)
        if start_date_obj is None:
            return {
                "status": "error",
                "message": "Invalid start date. Expected YYYY-MM-DD."
            }

    if end_date:
        end_date_obj = validate_date(end_date)
        if end_date_obj is None:
            return {
                "status": "error",
                "message": "Invalid end date. Expected YYYY-MM-DD."
            }

    if start_date_obj and end_date_obj:
        if start_date_obj > end_date_obj:
            return {
                "status": "error",
                "message": "Start date cannot be after end date."
            }

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

def calculate_total(start_date, end_date):

    query = text("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE date BETWEEN :start_date AND :end_date
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {
            "start_date": start_date,
            "end_date": end_date
        })

        return result.scalar_one()

def load_categories():
    with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_category_totals(start_date, end_date):

    query = text("""
        SELECT category, SUM(amount) AS total_amount
        FROM expenses
        WHERE date BETWEEN :start_date AND :end_date
        GROUP BY category
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {
            "start_date": start_date,
            "end_date": end_date
        })

        return dict(result.fetchall())

def calculate_category_statistics(expenses, threshold_multiplier=2.0):
    grouped_expenses = defaultdict(list)

    for expense in expenses:
        grouped_expenses[expense["category"]].append(expense["amount"])

    category_stats = {}

    for category, amounts in grouped_expenses.items():
        mean = statistics.mean(amounts)
        std_dev = statistics.pstdev(amounts)

        threshold = mean + (threshold_multiplier * std_dev)

        category_stats[category] = {
            "mean": round(mean, 2),
            "standard_deviation": round(std_dev, 2),
            "threshold": round(threshold, 2)
        }

    return category_stats


def fetch_expenses_for_analysis(start_date=None, end_date=None):

    query = """
        SELECT id, date, amount, category, subcategory, note
        FROM expenses
    """

    conditions = []
    params = {}

    if start_date:
        conditions.append("date >= :start_date")
        params["start_date"] = start_date

    if end_date:
        conditions.append("date <= :end_date")
        params["end_date"] = end_date

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY category, date"

    with engine.connect() as connection:
        result = connection.execute(text(query), params)

        return [
            dict(row)
            for row in result.mappings().all()
        ]
