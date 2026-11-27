
from datetime import date
from expensetrackermcp.app import mcp
from expensetrackermcp.utility_func import *
from expensetrackermcp.database import engine

from sqlalchemy import text


@mcp.tool()
async def get_total_expenses(start_date: str, end_date: str):
    """Calculate total expenses within a date range."""

    if not start_date or not end_date:
        return {
            "status": "error",
            "message": "Both start date and end date are required."
        }

    validation_error = validate_date_range(start_date, end_date)

    if validation_error:
        return validation_error

    # Convert strings into Python date objects for PostgreSQL DATE parameters.
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

        total = result.scalar_one()

    return {
        "status": "success",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_expenses": total
    }


@mcp.tool()
async def get_category_wise_expenses(
    start_date: str = None,
    end_date: str = None
):
    """Calculate category-wise expenses, optionally within a date range."""

    validation_error = validate_date_range(start_date, end_date)

    if validation_error:
        return validation_error

    if start_date:
        start_date = date.fromisoformat(start_date)

    if end_date:
        end_date = date.fromisoformat(end_date)

    query = """
        SELECT category, SUM(amount) AS total_amount
        FROM expenses
        WHERE 1=1
    """

    params = {}

    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    query += """
        GROUP BY category
        ORDER BY total_amount DESC
    """

    async with engine.connect() as connection:
        result = await connection.execute(text(query), params)

        category_totals = [
            dict(row)
            for row in result.mappings().all()
        ]

    return {
        "status": "success",
        "count": len(category_totals),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "category_breakdown": category_totals
    }


@mcp.tool()
async def get_average_expense(
    start_date: str = None,
    end_date: str = None
):
    """Calculate the average transaction amount, optionally within a date range."""

    validation_error = validate_date_range(start_date, end_date)

    if validation_error:
        return validation_error

    if start_date:
        start_date = date.fromisoformat(start_date)

    if end_date:
        end_date = date.fromisoformat(end_date)

    query = """
        SELECT
            COUNT(*) AS expense_count,
            COALESCE(SUM(amount), 0) AS total_amount,
            COALESCE(AVG(amount), 0) AS average_amount
        FROM expenses
        WHERE 1=1
    """

    params = {}

    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    async with engine.connect() as connection:
        result = await connection.execute(text(query), params)
        row = result.mappings().one()

        expense_count = row["expense_count"]
        total_amount = row["total_amount"]
        average_amount = row["average_amount"]

    return {
        "status": "success",
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "expense_count": expense_count,
        "total_amount": total_amount,
        "average_expense": round(average_amount, 2)
    }


@mcp.tool()
async def get_highest_lowest_expenses(
    start_date: str = None,
    end_date: str = None,
    category: str = None,
    subcategory: str = None
):
    """Find the highest and lowest individual expenses using optional filters."""

    validation_error = validate_date_range(start_date, end_date)

    if validation_error:
        return validation_error

    categories = load_categories()

    category_error = validate_category_filters(
        category, subcategory, categories
    )

    if category_error:
        return category_error

    if start_date:
        start_date = date.fromisoformat(start_date)

    if end_date:
        end_date = date.fromisoformat(end_date)

    query = """
        SELECT id, date, amount, category, subcategory, note
        FROM expenses
        WHERE 1=1
    """

    params = {}

    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    if category:
        query += " AND category = :category"
        params["category"] = category

    if subcategory:
        query += " AND subcategory = :subcategory"
        params["subcategory"] = subcategory

    async with engine.connect() as connection:
        highest_result = await connection.execute(
            text(query + " ORDER BY amount DESC, id ASC LIMIT 1"),
            params
        )

        highest = highest_result.mappings().first()

        lowest_result = await connection.execute(
            text(query + " ORDER BY amount ASC, id ASC LIMIT 1"),
            params
        )

        lowest = lowest_result.mappings().first()

    if highest is None:
        return {
            "status": "success",
            "message": "No expenses found for the given criteria.",
            "highest_expense": None,
            "lowest_expense": None
        }

    return {
        "status": "success",
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "category": category,
        "subcategory": subcategory,
        "highest_expense": dict(highest),
        "lowest_expense": dict(lowest)
    }


@mcp.tool()
async def get_monthly_spending_trends(
    start_date: str = None,
    end_date: str = None
):
    """Calculate monthly spending totals, optionally within a date range."""

    validation_error = validate_date_range(start_date, end_date)

    if validation_error:
        return validation_error

    if start_date:
        start_date = date.fromisoformat(start_date)

    if end_date:
        end_date = date.fromisoformat(end_date)

    query = """
        SELECT
            TO_CHAR(date, 'YYYY-MM') AS month,
            SUM(amount) AS total_amount,
            COUNT(*) AS expense_count
        FROM expenses
        WHERE 1=1
    """

    params = {}

    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    query += """
        GROUP BY TO_CHAR(date, 'YYYY-MM')
        ORDER BY month
    """

    async with engine.connect() as connection:
        result = await connection.execute(text(query), params)

        monthly_trends = [
            dict(row)
            for row in result.mappings().all()
        ]

    return {
        "status": "success",
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "count": len(monthly_trends),
        "monthly_trends": monthly_trends
    }


@mcp.tool()
async def get_spending_comparison(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str
):
    """Compare total expenses across two date ranges."""

    period1_error = validate_date_range(
        period1_start, period1_end
    )

    if period1_error:
        return period1_error

    period2_error = validate_date_range(
        period2_start, period2_end
    )

    if period2_error:
        return period2_error

    # These utility functions are async, so we must await them.
    period1_total = await calculate_total(
        period1_start, period1_end
    )

    period2_total = await calculate_total(
        period2_start, period2_end
    )

    difference = period2_total - period1_total

    if difference > 0:
        status = "increased"
    elif difference < 0:
        status = "decreased"
    else:
        status = "unchanged"

    if period1_total == 0:
        percentage_change = None
    else:
        percentage_change = round(
            (difference / period1_total) * 100, 2
        )

    return {
        "status": "success",
        "period1": {
            "start_date": period1_start,
            "end_date": period1_end,
            "total_expenses": period1_total
        },
        "period2": {
            "start_date": period2_start,
            "end_date": period2_end,
            "total_expenses": period2_total
        },
        "difference": difference,
        "percentage_change": percentage_change,
        "spending_trend": status
    }


@mcp.tool()
async def get_category_spending_comparison(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str
):
    """Compare category-wise expenses across two date ranges."""

    period1_error = validate_date_range(
        period1_start, period1_end
    )

    if period1_error:
        return period1_error

    period2_error = validate_date_range(
        period2_start, period2_end
    )

    if period2_error:
        return period2_error

    # These utility functions are async, so we must await them.
    period1_totals = await calculate_category_totals(
        period1_start, period1_end
    )

    period2_totals = await calculate_category_totals(
        period2_start, period2_end
    )

    all_categories = set(period1_totals) | set(period2_totals)

    category_comparison = []

    for category in sorted(all_categories):

        period1_amount = period1_totals.get(category, 0)
        period2_amount = period2_totals.get(category, 0)

        difference = period2_amount - period1_amount

        if difference > 0:
            trend = "increased"
        elif difference < 0:
            trend = "decreased"
        else:
            trend = "unchanged"

        if period1_amount == 0:
            percentage_change = None
        else:
            percentage_change = round(
                (difference / period1_amount) * 100, 2
            )

        category_comparison.append({
            "category": category,
            "period1_amount": period1_amount,
            "period2_amount": period2_amount,
            "difference": difference,
            "percentage_change": percentage_change,
            "trend": trend
        })

    return {
        "status": "success",
        "period1": {
            "start_date": period1_start,
            "end_date": period1_end
        },
        "period2": {
            "start_date": period2_start,
            "end_date": period2_end
        },
        "category_comparison": category_comparison
    }


@mcp.tool()
async def detect_unusual_spending(
    start_date: str = None,
    end_date: str = None,
    threshold_multiplier: float = 2.0
):
    """Detect unusually high expenses using category-wise standard deviation."""

    date_error = validate_date_range(start_date, end_date)

    if date_error:
        return date_error

    if threshold_multiplier <= 0:
        return {
            "status": "error",
            "message": "Threshold multiplier must be greater than zero."
        }

    # This utility function is async, so we must await it.
    expenses = await fetch_expenses_for_analysis(start_date, end_date)

    if not expenses:
        return {
            "status": "success",
            "message": "No expenses found for the given date range.",
            "unusual_expenses": []
        }

    category_stats = calculate_category_statistics(expenses)

    unusual_expenses = []

    for expense in expenses:
        stats = category_stats[expense["category"]]

        threshold = (
            stats["average"] +
            threshold_multiplier * stats["std_dev"]
        )

        if expense["amount"] > threshold:
            unusual_expenses.append({
                **expense,
                "category_average": stats["average"],
                "standard_deviation": stats["std_dev"],
                "anomaly_threshold": threshold
            })

    return {
        "status": "success",
        "threshold_multiplier": threshold_multiplier,
        "total_expenses_analyzed": len(expenses),
        "unusual_expense_count": len(unusual_expenses),
        "unusual_expenses": unusual_expenses
    }
