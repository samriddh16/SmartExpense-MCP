import sqlite3
from pathlib import Path
from app import mcp
from utility_func import *

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "expenses.db"

@mcp.tool()
def get_total_expenses(start_date: str, end_date: str):
    """Calculate total expenses within a date range."""

    if not start_date or not end_date:
        return {
            "status": "error",
            "message": "Both start date and end date are required."
        }

    validation_error = validate_date_range(start_date, end_date)

    if validation_error:
        return validation_error

    # Calculate total
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE date BETWEEN ? AND ?
            """,
            (start_date, end_date)
        )

        total = cur.fetchone()[0]

    return {
        "status": "success",
        "start_date": start_date,
        "end_date": end_date,
        "total_expenses": total
    }


@mcp.tool()
def get_category_wise_expenses(
    start_date: str = None,
    end_date: str = None
):
    """Calculate category-wise expenses, optionally within a date range."""

    validation_error = validate_date_range(start_date, end_date)

    if validation_error:
        return validation_error

    # Build query dynamically
    query = """
        SELECT category, SUM(amount) AS total_amount
        FROM expenses
        WHERE 1=1
    """

    params = []

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    query += """
        GROUP BY category
        ORDER BY total_amount DESC
    """

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(query, params)

        columns = [description[0] for description in cur.description]

        category_totals = [
            dict(zip(columns, row))
            for row in cur.fetchall()
        ]

    return {
        "status": "success",
        "count": len(category_totals),
        "start_date": start_date,
        "end_date": end_date,
        "category_breakdown": category_totals
    }


@mcp.tool()
def get_average_expense(
    start_date: str = None,
    end_date: str = None
):
    """Calculate the average transaction amount, optionally within a date range."""

    validation_error = validate_date_range(start_date, end_date)

    if validation_error:
        return validation_error

    # Build query dynamically
    query = """
        SELECT
            COUNT(*) AS expense_count,
            COALESCE(SUM(amount), 0) AS total_amount,
            COALESCE(AVG(amount), 0) AS average_amount
        FROM expenses
        WHERE 1=1
    """

    params = []

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(query, params)

        expense_count, total_amount, average_amount = cur.fetchone()

    return {
        "status": "success",
        "start_date": start_date,
        "end_date": end_date,
        "expense_count": expense_count,
        "total_amount": total_amount,
        "average_expense": round(average_amount, 2)
    }


@mcp.tool()
def get_highest_lowest_expenses(
    start_date: str = None,
    end_date: str = None,
    category: str = None,
    subcategory: str = None
):
    """Find the highest and lowest individual expenses using optional filters."""

    # Validate dates
    validation_error = validate_date_range(start_date, end_date)

    if validation_error:
        return validation_error

    # Validate category and subcategory
    categories = load_categories()

    category_error = validate_category_filters(
        category, subcategory, categories
    )

    if category_error:
        return category_error

    # Build the SQL query dynamically
    query = """
        SELECT id, date, amount, category, subcategory, note
        FROM expenses
        WHERE 1=1
    """

    params = []

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    if category:
        query += " AND category = ?"
        params.append(category)

    if subcategory:
        query += " AND subcategory = ?"
        params.append(subcategory)

    # Find highest and lowest expenses
    with sqlite3.connect(DB_PATH) as c:

        highest_cur = c.execute(
            query + " ORDER BY amount DESC, id ASC LIMIT 1",
            params
        )
        highest = highest_cur.fetchone()

        lowest_cur = c.execute(
            query + " ORDER BY amount ASC, id ASC LIMIT 1",
            params
        )
        lowest = lowest_cur.fetchone()

        columns = [
            description[0]
            for description in highest_cur.description
        ]

    if highest is None:
        return {
            "status": "success",
            "message": "No expenses found for the given criteria.",
            "highest_expense": None,
            "lowest_expense": None
        }

    return {
        "status": "success",
        "start_date": start_date,
        "end_date": end_date,
        "category": category,
        "subcategory": subcategory,
        "highest_expense": dict(zip(columns, highest)),
        "lowest_expense": dict(zip(columns, lowest))
    }



@mcp.tool()
def get_monthly_spending_trends(
    start_date: str = None,
    end_date: str = None
):
    """Calculate monthly spending totals, optionally within a date range."""

    validation_error = validate_date_range(start_date, end_date)

    if validation_error:
        return validation_error

    query = """
        SELECT
            strftime('%Y-%m', date) AS month,
            SUM(amount) AS total_amount,
            COUNT(*) AS expense_count
        FROM expenses
        WHERE 1=1
    """

    params = []

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    query += """
        GROUP BY strftime('%Y-%m', date)
        ORDER BY month
    """

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(query, params)

        columns = [
            description[0]
            for description in cur.description
        ]

        monthly_trends = [
            dict(zip(columns, row))
            for row in cur.fetchall()
        ]

    return {
        "status": "success",
        "start_date": start_date,
        "end_date": end_date,
        "count": len(monthly_trends),
        "monthly_trends": monthly_trends
    }

@mcp.tool()
def get_spending_comparison(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str
):
    """Compare total expenses across two date ranges."""

    # Validate first period
    period1_error = validate_date_range(
        period1_start, period1_end
    )

    if period1_error:
        return period1_error

    # Validate second period
    period2_error = validate_date_range(
        period2_start, period2_end
    )

    if period2_error:
        return period2_error

    # Calculate spending for both periods
    period1_total = calculate_total(
        period1_start, period1_end
    )

    period2_total = calculate_total(
        period2_start, period2_end
    )

    # Calculate absolute difference
    difference = period2_total - period1_total

    # Determine spending status
    if difference > 0:
        status = "increased"
    elif difference < 0:
        status = "decreased"
    else:
        status = "unchanged"

    # Calculate percentage change
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
def get_category_spending_comparison(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str
):
    """Compare category-wise expenses across two date ranges."""

    # Validate first period
    period1_error = validate_date_range(
        period1_start, period1_end
    )

    if period1_error:
        return period1_error

    # Validate second period
    period2_error = validate_date_range(
        period2_start, period2_end
    )

    if period2_error:
        return period2_error

    # Calculate category-wise totals for both periods
    period1_totals = calculate_category_totals(
        period1_start, period1_end
    )

    period2_totals = calculate_category_totals(
        period2_start, period2_end
    )

    # Get all categories from both periods
    all_categories = set(period1_totals) | set(period2_totals)

    category_comparison = []

    # Compare each category
    for category in sorted(all_categories):

        period1_amount = period1_totals.get(category, 0)
        period2_amount = period2_totals.get(category, 0)

        difference = period2_amount - period1_amount

        # Determine spending trend
        if difference > 0:
            trend = "increased"
        elif difference < 0:
            trend = "decreased"
        else:
            trend = "unchanged"

        # Calculate percentage change
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