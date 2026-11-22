from app import mcp
from utility_func import *
from datetime import datetime
import math

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "expenses.db"


def create_budget_table():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                month TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                UNIQUE(category, month)
            )
        """)


create_budget_table()

@mcp.tool()
def set_category_budget(category: str, month: str, amount: float):
    """Set or update a monthly budget for a category."""

    categories = load_categories()

    if category not in categories:
        return {
            "status": "error",
            "message": f"Invalid category: {category}"
        }

    try:
        datetime.strptime(month, "%Y-%m")
    except (ValueError, TypeError):
        return {
            "status": "error",
            "message": "Invalid month. Expected YYYY-MM."
        }

    if not math.isfinite(amount) or amount <= 0:
        return {
            "status": "error",
            "message": "Budget amount must be a finite number greater than zero."
        }

    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            INSERT INTO budgets (category, month, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(category, month)
            DO UPDATE SET amount = excluded.amount
        """, (category, month, amount))

    return {
        "status": "success",
        "message": f"Budget set successfully for {category} in {month}.",
        "category": category,
        "month": month,
        "budget_amount": amount
    }


@mcp.tool()
def get_remaining_budget(category: str, month: str):
    """Get the remaining monthly budget for a category."""

    categories = load_categories()

    if category not in categories:
        return {
            "status": "error",
            "message": f"Invalid category: {category}"
        }

    if not isinstance(month, str) or len(month) != 7 or month[4] != "-":
        return {
            "status": "error",
            "message": "Invalid month. Expected YYYY-MM."
        }

    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        return {
            "status": "error",
            "message": "Invalid month. Expected YYYY-MM."
        }

    with sqlite3.connect(DB_PATH) as c:
        budget = c.execute("""
            SELECT amount
            FROM budgets
            WHERE category = ? AND month = ?
        """, (category, month)).fetchone()

        if budget is None:
            return {
                "status": "error",
                "message": f"No budget found for {category} in {month}."
            }

        spent = c.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE category = ?
            AND strftime('%Y-%m', date) = ?
        """, (category, month)).fetchone()[0]

    budget_amount = budget[0]
    remaining = budget_amount - spent

    return {
        "status": "success",
        "category": category,
        "month": month,
        "budget_amount": budget_amount,
        "spent_amount": round(spent, 2),
        "remaining_amount": round(remaining, 2),
        "is_over_budget": remaining < 0
    }


@mcp.tool()
def get_budget_usage(month: str):
    """Get monthly budget usage across all budgeted categories."""

    if not isinstance(month, str) or len(month) != 7 or month[4] != "-":
        return {
            "status": "error",
            "message": "Invalid month. Expected YYYY-MM."
        }

    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        return {
            "status": "error",
            "message": "Invalid month. Expected YYYY-MM."
        }

    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row

        records = c.execute("""
            SELECT
                b.category,
                b.amount AS budget_amount,
                COALESCE(SUM(e.amount), 0) AS spent_amount
            FROM budgets b
            LEFT JOIN expenses e
                ON b.category = e.category
                AND strftime('%Y-%m', e.date) = b.month
            WHERE b.month = ?
            GROUP BY b.category, b.amount
            ORDER BY b.category
        """, (month,)).fetchall()

    if not records:
        return {
            "status": "success",
            "message": f"No budgets found for {month}.",
            "budget_usage": []
        }

    budget_usage = []

    for record in records:
        budget_amount = record["budget_amount"]
        spent_amount = record["spent_amount"]

        usage_percentage = (spent_amount / budget_amount) * 100

        budget_usage.append({
            "category": record["category"],
            "budget_amount": budget_amount,
            "spent_amount": round(spent_amount, 2),
            "remaining_amount": round(budget_amount - spent_amount, 2),
            "usage_percentage": round(usage_percentage, 2),
            "is_over_budget": spent_amount > budget_amount
        })

    return {
        "status": "success",
        "month": month,
        "total_categories": len(budget_usage),
        "budget_usage": budget_usage
    }


@mcp.tool()
def check_budget_overruns(month: str):
    """Identify categories that have exceeded their monthly budgets."""

    if not isinstance(month, str) or len(month) != 7 or month[4] != "-":
        return {
            "status": "error",
            "message": "Invalid month. Expected YYYY-MM."
        }

    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        return {
            "status": "error",
            "message": "Invalid month. Expected YYYY-MM."
        }

    with sqlite3.connect(DB_PATH) as c:
        records = c.execute("""
            SELECT
                b.category,
                b.amount AS budget_amount,
                COALESCE(SUM(e.amount), 0) AS spent_amount
            FROM budgets b
            LEFT JOIN expenses e
                ON b.category = e.category
                AND strftime('%Y-%m', e.date) = b.month
            WHERE b.month = ?
            GROUP BY b.category, b.amount
            HAVING SUM(COALESCE(e.amount, 0)) > b.amount
            ORDER BY (SUM(COALESCE(e.amount, 0)) - b.amount) DESC
        """, (month,)).fetchall()

    overruns = []

    for category, budget_amount, spent_amount in records:
        overruns.append({
            "category": category,
            "budget_amount": budget_amount,
            "spent_amount": round(spent_amount, 2),
            "overrun_amount": round(spent_amount - budget_amount, 2),
            "overrun_percentage": round(
                (spent_amount - budget_amount) / budget_amount * 100, 2
            )
        })

    return {
        "status": "success",
        "month": month,
        "overrun_count": len(overruns),
        "overruns": overruns
    }