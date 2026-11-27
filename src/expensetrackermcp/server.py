
from expensetrackermcp.app import mcp
import expensetrackermcp.analytics_func
import expensetrackermcp.budget_func

from expensetrackermcp.utility_func import *
from expensetrackermcp.database import engine

from sqlalchemy import text
from importlib.resources import files


CATEGORIES_FILE = files(
    "expensetrackermcp.resources"
).joinpath("categories.json")


@mcp.tool()
def add_expense(date, amount, category, subcategory="", note=""):
    """Add a new expense entry to the database."""
    query = text("""
        INSERT INTO expenses(date, amount, category, subcategory, note)
        VALUES (:date, :amount, :category, :subcategory, :note)
        RETURNING id
    """)

    with engine.begin() as connection:
        result = connection.execute(query, {
            "date": date,
            "amount": amount,
            "category": category,
            "subcategory": subcategory,
            "note": note
        })

        expense_id = result.scalar_one()

    return {"status": "ok", "id": expense_id}


@mcp.tool()
def list_expenses(start_date, end_date):
    """List expense entries within an inclusive date range."""
    query = text("""
        SELECT id, date, amount, category, subcategory, note
        FROM expenses
        WHERE date BETWEEN :start_date AND :end_date
        ORDER BY id ASC
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {
            "start_date": start_date,
            "end_date": end_date
        })

        return [dict(row) for row in result.mappings().all()]


@mcp.tool()
def summarize(start_date, end_date, category=None):
    """Summarize expenses by category within an inclusive date range."""
    query = """
        SELECT category, SUM(amount) AS total_amount
        FROM expenses
        WHERE date BETWEEN :start_date AND :end_date
    """

    params = {
        "start_date": start_date,
        "end_date": end_date
    }

    if category:
        query += " AND category = :category"
        params["category"] = category

    query += " GROUP BY category ORDER BY category ASC"

    with engine.connect() as connection:
        result = connection.execute(text(query), params)
        return [dict(row) for row in result.mappings().all()]


@mcp.tool()
def filter_expenses(
    start_date: str = None,
    end_date: str = None,
    category: str = None,
    subcategory: str = None
):
    """Filter expenses using optional date and category filters."""

    category = category.strip().lower() if category else None
    subcategory = subcategory.strip().lower() if subcategory else None

    validation_error = validate_filter_inputs(
        start_date, end_date, category, subcategory
    )

    if validation_error:
        return validation_error

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

    with engine.connect() as connection:
        result = connection.execute(text(query), params)
        expenses = [dict(row) for row in result.mappings().all()]

    return {
        "status": "success",
        "count": len(expenses),
        "message": (
            "Expenses retrieved successfully."
            if expenses else "No matching expenses found."
        ),
        "expenses": expenses
    }


@mcp.tool()
def search_expenses_by_note(keyword: str):
    """Search expenses using keywords in their notes."""

    if not keyword or not keyword.strip():
        return {
            "status": "error",
            "message": "Please provide a valid search keyword."
        }

    query = text("""
        SELECT id, date, amount, category, subcategory, note
        FROM expenses
        WHERE note ILIKE :keyword
        ORDER BY id
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {
            "keyword": f"%{keyword.strip()}%"
        })

        expenses = [dict(row) for row in result.mappings().all()]

    return {
        "status": "success",
        "count": len(expenses),
        "message": (
            "Matching expenses found."
            if expenses else "No matching expenses found."
        ),
        "expenses": expenses
    }


@mcp.tool()
def delete_expense(expense_id: int):
    """Delete an expense using its ID."""

    with engine.begin() as connection:
        result = connection.execute(
            text("DELETE FROM expenses WHERE id = :expense_id"),
            {"expense_id": expense_id}
        )

        if result.rowcount == 0:
            return {
                "status": "error",
                "message": f"No expense found with ID {expense_id}."
            }

    return {
        "status": "success",
        "message": f"Expense {expense_id} deleted successfully."
    }


@mcp.tool()
def delete_all_expenses(confirmed: bool = False):
    """Delete all expenses after explicit confirmation."""

    if not confirmed:
        return {
            "status": "confirmation_required",
            "message": "Please confirm before deleting all expenses."
        }

    with engine.begin() as connection:
        result = connection.execute(
            text("DELETE FROM expenses")
        )
        deleted_count = result.rowcount

    return {
        "status": "success",
        "deleted_count": deleted_count,
        "message": f"Deleted {deleted_count} expenses successfully."
    }


@mcp.tool()
def update_expense(
    expense_id: int,
    date: str = None,
    amount: float = None,
    category: str = None,
    subcategory: str = None,
    note: str = None
):
    """Update an existing expense."""

    updates, error = validate_update_fields(
        date, amount, category, subcategory, note
    )

    if error:
        return error

    if not updates:
        return {
            "status": "error",
            "message": "No fields provided to update."
        }

    with engine.begin() as connection:
        result = connection.execute(
            text("SELECT id FROM expenses WHERE id = :expense_id"),
            {"expense_id": expense_id}
        )

        if result.fetchone() is None:
            return {
                "status": "error",
                "message": f"No expense found with ID {expense_id}."
            }

        set_clause = ", ".join(
            f"{column} = :{column}"
            for column in updates
        )

        params = dict(updates)
        params["expense_id"] = expense_id

        query = text(f"""
            UPDATE expenses
            SET {set_clause}
            WHERE id = :expense_id
        """)

        connection.execute(query, params)

    return {
        "status": "success",
        "message": f"Expense {expense_id} updated successfully.",
        "updated_fields": list(updates.keys())
    }


@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    """Return the available expense categories."""
    return CATEGORIES_FILE.read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8050)
