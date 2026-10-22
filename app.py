

import os
from datetime import date
from collections import Counter

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, abort
)

from database import (
    initialize_database,
    get_departments,
    get_visits,
    get_visit,
    add_visit,
    update_visit,
    delete_visit
)

app = Flask(__name__)
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "hospital-dashboard-local-key"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(CHART_DIR, exist_ok=True)

VISIT_TYPES = ["Outpatient", "Inpatient", "Emergency"]

# Teal color for all charts
CHART_COLOR = "#14B8A6"


def make_chart(filename, title, labels, values, color=CHART_COLOR):
    plt.figure(figsize=(7, 3.5))
    plt.bar(labels, values, color=color, edgecolor="white")
    plt.title(title, fontsize=13, color=CHART_COLOR)
    plt.ylabel("Number of visits")
    plt.xticks(rotation=25, ha="right")
    plt.grid(axis="y", alpha=0.2)
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, filename), dpi=130)
    plt.close()


def valid_age(value):
    """Return an integer age from 0 to 120, or None if invalid."""
    try:
        age = int(value)
        if 0 <= age <= 120:
            return age
    except (TypeError, ValueError):
        pass
    return None


@app.route("/")
def index():
    return render_template(
        "index.html",
        departments=get_departments(),
        visit_types=VISIT_TYPES,
        today=date.today().isoformat()
    )


@app.route("/add_visit", methods=["POST"])
def add_visit_route():
    patient_name = request.form.get("patient_name", "").strip()
    age_input = request.form.get("age", "").strip()
    gender = request.form.get("gender", "Not specified").strip()
    department_input = request.form.get("department_id", "").strip()
    visit_date = request.form.get("visit_date", "").strip()
    visit_type = request.form.get("visit_type", "").strip()

    age = valid_age(age_input)

    if not patient_name:
        flash("Please enter the patient name.", "error")
        return redirect(url_for("index"))

    if age_input == "" or age is None:
        flash("Please enter a valid age between 0 and 120.", "error")
        return redirect(url_for("index"))

    if not all([department_input, visit_date, visit_type]):
        flash("Please complete all required fields.", "error")
        return redirect(url_for("index"))

    if visit_type not in VISIT_TYPES:
        flash("Please select a valid visit type.", "error")
        return redirect(url_for("index"))

    try:
        department_id = int(department_input)

        patient_id = add_visit(
            age,
            gender or "Not specified",
            department_id,
            visit_date,
            visit_type,
            patient_name
        )

        flash(
            f"Visit added successfully! Patient ID: P{patient_id:04d}",
            "success"
        )

    except Exception:
        app.logger.exception("Unable to add visit")
        flash(
            "Unable to add visit. Please check the details and database.",
            "error"
        )

    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    records = get_visits()

    total_visits = len(records)
    active_departments = len(
        set(record["department_id"] for record in records)
    )

    if records:
        dates = [record["visit_date"] for record in records]
        unique_days = max(len(set(dates)), 1)
        average_daily_visits = round(total_visits / unique_days, 1)
    else:
        average_daily_visits = 0

    department_counts = Counter(
        record["department_name"] for record in records
    )

    make_chart(
        "department_chart.png",
        "Visits by Department",
        list(department_counts.keys()) or ["No data"],
        list(department_counts.values()) or [0]
    )

    monthly_counts = Counter(
        record["visit_date"].strftime("%Y-%m")
        for record in records
    )

    monthly_labels = sorted(monthly_counts)

    make_chart(
        "monthly_chart.png",
        "Monthly Visits",
        monthly_labels or ["No data"],
        [monthly_counts[month] for month in monthly_labels] or [0]
    )

    # Display exact ages in the chart.
    age_counts = Counter(
        str(record["age"]) if record["age"] is not None else "Not entered"
        for record in records
    )

    age_labels = sorted(
        [age for age in age_counts if age != "Not entered"],
        key=int
    )

    if "Not entered" in age_counts:
        age_labels.append("Not entered")

    make_chart(
        "age_chart.png",
        "Visits by Exact Age",
        age_labels or ["No data"],
        [age_counts[age] for age in age_labels] or [0]
    )

    visit_type_counts = Counter(
        record["visit_type"] for record in records
    )

    return render_template(
        "dashboard.html",
        total_visits=total_visits,
        active_departments=active_departments,
        average_daily_visits=average_daily_visits,
        department_counts=department_counts,
        monthly_counts=monthly_counts,
        age_counts=age_counts,
        visit_type_counts=visit_type_counts,
        recent_visits=records[:5]
    )


@app.route("/history")
def history():
    filters = {
        "q": request.args.get("q", "").strip(),
        "department_id": request.args.get("department_id", ""),
        "visit_type": request.args.get("visit_type", ""),
        "start_date": request.args.get("start_date", ""),
        "end_date": request.args.get("end_date", "")
    }

    records = get_visits(filters)

    return render_template(
        "history.html",
        records=records,
        departments=get_departments(),
        visit_types=VISIT_TYPES,
        filters=filters
    )


@app.route("/edit/<int:visit_id>", methods=["GET", "POST"])
def edit(visit_id):
    record = get_visit(visit_id)

    if not record:
        abort(404)

    if request.method == "POST":
        patient_name = request.form.get("patient_name", "").strip()
        age_input = request.form.get("age", "").strip()
        age = valid_age(age_input)

        if not patient_name:
            flash("Please enter the patient name.", "error")
            return redirect(url_for("edit", visit_id=visit_id))

        if age_input == "" or age is None:
            flash("Please enter a valid age between 0 and 120.", "error")
            return redirect(url_for("edit", visit_id=visit_id))

        try:
            department_id = int(request.form["department_id"])
            visit_date = request.form["visit_date"]
            visit_type = request.form["visit_type"]
            gender = request.form.get("gender", "Not specified").strip()

            if visit_type not in VISIT_TYPES:
                raise ValueError("Invalid visit type")

            update_visit(
                visit_id,
                record["patient_id"],
                age,
                gender or "Not specified",
                department_id,
                visit_date,
                visit_type,
                patient_name
            )

            flash("Visit updated successfully!", "success")
            return redirect(url_for("history"))

        except Exception:
            app.logger.exception("Unable to update visit")
            flash(
                "Unable to update visit. Please check the details.",
                "error"
            )

    return render_template(
        "edit.html",
        record=record,
        departments=get_departments(),
        visit_types=VISIT_TYPES,
        today=date.today().isoformat()
    )


@app.route("/delete/<int:visit_id>", methods=["POST"])
def delete(visit_id):
    try:
        delete_visit(visit_id)
        flash("Visit deleted successfully.", "success")

    except Exception:
        app.logger.exception("Unable to delete visit")
        flash("Unable to delete visit.", "error")

    return redirect(url_for("history"))


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
