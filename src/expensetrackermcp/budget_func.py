
from expensetrackermcp.app import mcp
from expensetrackermcp.utility_func import load_categories
from expensetrackermcp.database import engine

from sqlalchemy import text
from datetime import datetime
import math


@mcp.tool()
async def set_category_budget(category: str, month: str, amount: float):
    """Set or update a monthly budget for a category."""

    categories = load_categories()

    if category not in categories:
        return {
            "status": "error",
            "message": f"Invalid category: **{category}**"
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

    query = text("""
        INSERT INTO budgets (category, month, amount)
        VALUES (:category, :month, :amount)
        ON CONFLICT (category, month)
        DO UPDATE SET amount = EXCLUDED.amount
    """)

    async with engine.begin() as connection:
        await connection.execute(query, {
            "category": category,
            "month": month,
            "amount": amount
        })

    return {
        "status": "success",
        "message": f"Budget set successfully for **{category}** in **{month}**.",
        "category": category,
        "month": month,
        "budget_amount": amount
    }


@mcp.tool()
async def get_remaining_budget(category: str, month: str):
    """Get the remaining monthly budget for a category."""

    categories = load_categories()

    if category not in categories:
        return {
            "status": "error",
            "message": f"Invalid category: **{category}**"
        }

    try:
        datetime.strptime(month, "%Y-%m")
    except (ValueError, TypeError):
        return {
            "status": "error",
            "message": "Invalid month. Expected YYYY-MM."
        }

    budget_query = text("""
        SELECT amount
        FROM budgets
        WHERE category = :category AND month = :month
    """)

    spending_query = text("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE category = :category
        AND TO_CHAR(date, 'YYYY-MM') = :month
    """)

    async with engine.connect() as connection:
        budget = await connection.execute(
            budget_query,
            {"category": category, "month": month}
        )

        budget = budget.scalar_one_or_none()

        if budget is None:
            return {
                "status": "error",
                "message": f"No budget found for **{category}** in **{month}**."
            }

        spent = await connection.execute(
            spending_query,
            {"category": category, "month": month}
        )

        spent = spent.scalar_one()

    remaining = budget - spent

    return {
        "status": "success",
        "category": category,
        "month": month,
        "budget_amount": budget,
        "spent_amount": round(spent, 2),
        "remaining_amount": round(remaining, 2),
        "is_over_budget": remaining < 0
    }


@mcp.tool()
async def get_budget_usage(month: str):
    """Get monthly budget usage across all budgeted categories."""

    try:
        datetime.strptime(month, "%Y-%m")
    except (ValueError, TypeError):
        return {
            "status": "error",
            "message": "Invalid month. Expected YYYY-MM."
        }

    query = text("""
        SELECT
            b.category,
            b.amount AS budget_amount,
            COALESCE(SUM(e.amount), 0) AS spent_amount
        FROM budgets b
        LEFT JOIN expenses e
            ON b.category = e.category
            AND TO_CHAR(e.date, 'YYYY-MM') = b.month
        WHERE b.month = :month
        GROUP BY b.category, b.amount
        ORDER BY b.category
    """)

    async with engine.connect() as connection:
        result = await connection.execute(
            query, {"month": month}
        )
        records = result.mappings().all()

    if not records:
        return {
            "status": "success",
            "message": f"No budgets found for **{month}**.",
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
async def check_budget_overruns(month: str):
    """Identify categories that have exceeded their monthly budgets."""

    try:
        datetime.strptime(month, "%Y-%m")
    except (ValueError, TypeError):
        return {
            "status": "error",
            "message": "Invalid month. Expected YYYY-MM."
        }

    query = text("""
        SELECT
            b.category,
            b.amount AS budget_amount,
            COALESCE(SUM(e.amount), 0) AS spent_amount
        FROM budgets b
        LEFT JOIN expenses e
            ON b.category = e.category
            AND TO_CHAR(e.date, 'YYYY-MM') = b.month
        WHERE b.month = :month
        GROUP BY b.category, b.amount
        HAVING COALESCE(SUM(e.amount), 0) > b.amount
        ORDER BY (COALESCE(SUM(e.amount), 0) - b.amount) DESC
    """)

    async with engine.connect() as connection:
        result = await connection.execute(
            query, {"month": month}
        )
        records = result.mappings().all()

    overruns = []

    for record in records:
        budget_amount = record["budget_amount"]
        spent_amount = record["spent_amount"]

        overruns.append({
            "category": record["category"],
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
