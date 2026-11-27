import json
from datetime import date
from statistics import mean, pstdev
from collections import defaultdict
from datetime import datetime
from importlib.resources import files
from sqlalchemy import text
from expensetrackermcp.database import engine

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


async def calculate_total(start_date, end_date):
    start_date = date.fromisoformat(start_date)
    end_date = date.fromisoformat(end_date)

    query = text("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE date BETWEEN :start_date AND :end_date
    """)

    async with engine.connect() as connection:
        result = await connection.execute(query, {
            "start_date": start_date,
            "end_date": end_date
        })

        return result.scalar_one()


async def calculate_category_totals(start_date, end_date):
    start_date = date.fromisoformat(start_date)
    end_date = date.fromisoformat(end_date)

    query = text("""
        SELECT category, SUM(amount) AS total_amount
        FROM expenses
        WHERE date BETWEEN :start_date AND :end_date
        GROUP BY category
    """)

    async with engine.connect() as connection:
        result = await connection.execute(query, {
            "start_date": start_date,
            "end_date": end_date
        })

        return dict(result.fetchall())


async def fetch_expenses_for_analysis(start_date=None, end_date=None):
    query = """
        SELECT id, date, amount, category, subcategory, note
        FROM expenses
    """

    conditions = []
    params = {}

    if start_date:
        start_date = date.fromisoformat(start_date)
        conditions.append("date >= :start_date")
        params["start_date"] = start_date

    if end_date:
        end_date = date.fromisoformat(end_date)
        conditions.append("date <= :end_date")
        params["end_date"] = end_date

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY category, date"

    async with engine.connect() as connection:
        result = await connection.execute(text(query), params)

        return [
            dict(row)
            for row in result.mappings().all()
        ]


def calculate_category_statistics(expenses):
    category_expenses = defaultdict(list)

    for expense in expenses:
        category_expenses[expense["category"]].append(
            expense["amount"]
        )

    statistics = {}

    for category, amounts in category_expenses.items():
        avg = mean(amounts)
        std_dev = pstdev(amounts) if len(amounts) > 1 else 0

        statistics[category] = {
            "average": avg,
            "std_dev": std_dev,
            "count": len(amounts)
        }

    return statistics


def detect_unusual_expenses(expenses, multiplier=2):
    category_stats = calculate_category_statistics(expenses)

    unusual_expenses = []

    for expense in expenses:
        category = expense["category"]
        stats = category_stats[category]

        threshold = (
            stats["average"] +
            multiplier * stats["std_dev"]
        )

        if expense["amount"] > threshold:
            unusual_expenses.append({
                **expense,
                "threshold": threshold
            })

    return unusual_expenses


def load_categories():
    with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
