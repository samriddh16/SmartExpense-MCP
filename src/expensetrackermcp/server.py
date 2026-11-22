from app import mcp
import analytics_func
import budget_func
from utility_func import *
import sqlite3
from pathlib import Path
from importlib.resources import files

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "expenses.db"


CATEGORIES_FILE = files(
    "expensetrackermcp.resources"
).joinpath("categories.json")


def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)


init_db()


@mcp.tool()
def add_expense(date, amount, category, subcategory="", note=""):
    '''Add a new expense entry to the database.'''
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
            (date, amount, category, subcategory, note)
        )
        return {"status": "ok", "id": cur.lastrowid}


@mcp.tool()
def list_expenses(start_date, end_date):
    '''List expense entries within an inclusive date range.'''
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY id ASC
            """,
            (start_date, end_date)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


@mcp.tool()
def summarize(start_date, end_date, category=None):
    '''Summarize expenses by category within an inclusive date range.'''
    with sqlite3.connect(DB_PATH) as c:
        query = (
            """
            SELECT category, SUM(amount) AS total_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
            """
        )
        params = [start_date, end_date]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " GROUP BY category ORDER BY category ASC"

        cur = c.execute(query, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    if start_date_obj > end_date_obj:
        return {
            "status": "error",
            "message": "Start date cannot be after end date."
        }

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

    # Execute the query
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(query, params)

        cols = [d[0] for d in cur.description]
        expenses = [
            dict(zip(cols, row))
            for row in cur.fetchall()
        ]

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

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE note LIKE ?
            ORDER BY id
            """,
            (f"%{keyword.strip()}%",)
        )

        columns = [description[0] for description in cur.description]

        expenses = [
            dict(zip(columns, row))
            for row in cur.fetchall()
        ]

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

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            "SELECT id FROM expenses WHERE id = ?",
            (expense_id,)
        )

        expense = cur.fetchone()

        if expense is None:
            return {
                "status": "error",
                "message": f"No expense found with ID {expense_id}."
            }

        c.execute(
            "DELETE FROM expenses WHERE id = ?",
            (expense_id,)
        )

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

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute("DELETE FROM expenses")
        deleted_count = cur.rowcount

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

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            "SELECT id FROM expenses WHERE id = ?",
            (expense_id,)
        )

        if cur.fetchone() is None:
            return {
                "status": "error",
                "message": f"No expense found with ID {expense_id}."
            }

        set_clause = ", ".join(
            f"{column} = ?"
            for column in updates
        )

        values = list(updates.values())
        values.append(expense_id)

        query = f"""
            UPDATE expenses
            SET {set_clause}
            WHERE id = ?
        """

        c.execute(query, values)

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
    mcp.run(transport="stdio")