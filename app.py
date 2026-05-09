from datetime import datetime
import os
import sqlite3
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "change-this-secret-key-in-production"
)


def get_db():
    """Open one SQLite connection per request."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Close the database connection after each request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create database tables if they do not exist."""
    db = sqlite3.connect(DATABASE_PATH)
    cursor = db.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            goal_text TEXT NOT NULL,
            goal_type TEXT NOT NULL CHECK(goal_type IN ('daily', 'weekly', 'monthly')),
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )

    db.commit()
    db.close()


def login_required(view_function):
    """Protect routes that should only be visible to logged-in users."""

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)

    return wrapped_view


def get_goal_groups(user_id):
    """Return goals grouped by type plus progress counts."""
    db = get_db()
    goals = db.execute(
        """
        SELECT id, user_id, goal_text, goal_type, completed, created_at
        FROM goals
        WHERE user_id = ?
        ORDER BY completed ASC, id DESC
        """,
        (user_id,),
    ).fetchall()

    grouped_goals = {"daily": [], "weekly": [], "monthly": []}
    for goal in goals:
        grouped_goals[goal["goal_type"]].append(goal)

    stats = {}
    total_completed = 0
    total_goals = 0

    for goal_type, items in grouped_goals.items():
        completed_count = sum(item["completed"] for item in items)
        total_count = len(items)
        progress = int((completed_count / total_count) * 100) if total_count else 0

        stats[goal_type] = {
            "completed": completed_count,
            "total": total_count,
            "progress": progress,
        }

        total_completed += completed_count
        total_goals += total_count

    stats["overall"] = {
        "completed": total_completed,
        "total": total_goals,
        "progress": int((total_completed / total_goals) * 100) if total_goals else 0,
    }

    return grouped_goals, stats


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not password or not confirm_password:
            flash("Please fill in all fields.", "error")
            return render_template("register.html")

        if len(username) < 3:
            flash("Username must be at least 3 characters long.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        db = get_db()
        existing_user = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if existing_user:
            flash("That username is already taken.", "error")
            return render_template("register.html")

        db.execute(
            """
            INSERT INTO users (username, password, created_at)
            VALUES (?, ?, ?)
            """,
            (
                username,
                generate_password_hash(password),
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        db.commit()

        flash("Account created successfully. You can log in now.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Enter both username and password.", "error")
            return render_template("login.html")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if user is None or not check_password_hash(user["password"], password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]

        flash("Welcome back.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    grouped_goals, stats = get_goal_groups(session["user_id"])
    return render_template(
        "dashboard.html",
        username=session.get("username", "User"),
        grouped_goals=grouped_goals,
        stats=stats,
    )


@app.route("/add_goal", methods=["POST"])
@login_required
def add_goal():
    goal_text = request.form.get("goal_text", "").strip()
    goal_type = request.form.get("goal_type", "").strip().lower()

    if not goal_text:
        flash("Goal text cannot be empty.", "error")
        return redirect(url_for("dashboard"))

    if goal_type not in {"daily", "weekly", "monthly"}:
        flash("Invalid goal type selected.", "error")
        return redirect(url_for("dashboard"))

    db = get_db()
    db.execute(
        """
        INSERT INTO goals (user_id, goal_text, goal_type, completed, created_at)
        VALUES (?, ?, ?, 0, ?)
        """,
        (
            session["user_id"],
            goal_text,
            goal_type,
            datetime.utcnow().isoformat(timespec="seconds"),
        ),
    )
    db.commit()

    flash(f"{goal_type.capitalize()} goal added.", "success")
    return redirect(url_for("dashboard"))


@app.route("/toggle_complete/<int:goal_id>", methods=["POST"])
@login_required
def toggle_complete(goal_id):
    db = get_db()
    goal = db.execute(
        "SELECT id, completed FROM goals WHERE id = ? AND user_id = ?",
        (goal_id, session["user_id"]),
    ).fetchone()

    if goal is None:
        flash("Goal not found.", "error")
        return redirect(url_for("dashboard"))

    new_value = 0 if goal["completed"] else 1
    db.execute(
        "UPDATE goals SET completed = ? WHERE id = ? AND user_id = ?",
        (new_value, goal_id, session["user_id"]),
    )
    db.commit()

    flash("Goal updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/delete_goal/<int:goal_id>", methods=["POST"])
@login_required
def delete_goal(goal_id):
    db = get_db()
    result = db.execute(
        "DELETE FROM goals WHERE id = ? AND user_id = ?",
        (goal_id, session["user_id"]),
    )
    db.commit()

    if result.rowcount == 0:
        flash("Goal not found.", "error")
    else:
        flash("Goal deleted.", "success")

    return redirect(url_for("dashboard"))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
