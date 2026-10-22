


import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "hospital_analytics")
    )


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                department_id INT AUTO_INCREMENT PRIMARY KEY,
                department_name VARCHAR(100) NOT NULL UNIQUE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id INT AUTO_INCREMENT PRIMARY KEY,
                patient_name VARCHAR(150) NOT NULL DEFAULT '',
                age_band VARCHAR(20) NULL,
                gender_optional VARCHAR(20) DEFAULT 'Not specified',
                age INT NULL
            )
        """)

        # Add patient_name to an existing patients table if missing.
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'patients'
              AND COLUMN_NAME = 'patient_name'
        """)

        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE patients
                ADD COLUMN patient_name VARCHAR(150)
                NOT NULL DEFAULT ''
            """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                visit_id INT AUTO_INCREMENT PRIMARY KEY,
                patient_id INT NOT NULL,
                department_id INT NOT NULL,
                visit_date DATE NOT NULL,
                visit_type VARCHAR(50) NOT NULL,
                FOREIGN KEY (patient_id)
                    REFERENCES patients(patient_id),
                FOREIGN KEY (department_id)
                    REFERENCES departments(department_id)
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM departments")

        if cursor.fetchone()[0] == 0:
            departments = [
                ("Cardiology",),
                ("Neurology",),
                ("Pediatrics",),
                ("Orthopedics",),
                ("General Medicine",),
                ("Dermatology",)
            ]

            cursor.executemany(
                "INSERT INTO departments (department_name) VALUES (%s)",
                departments
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def get_departments():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT department_id, department_name
            FROM departments
            ORDER BY department_name
        """)
        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def get_visits(filters=None):
    filters = filters or {}

    query = """
        SELECT
            v.visit_id,
            v.patient_id,
            p.patient_name,
            p.age,
            p.gender_optional AS gender,
            v.department_id,
            d.department_name,
            v.visit_date,
            v.visit_type
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        JOIN departments d ON v.department_id = d.department_id
        WHERE 1 = 1
    """

    params = []

    if filters.get("q"):
        search = f"%{filters['q']}%"
        query += """
            AND (
                CAST(v.visit_id AS CHAR) LIKE %s
                OR CAST(v.patient_id AS CHAR) LIKE %s
                OR p.patient_name LIKE %s
                OR CAST(p.age AS CHAR) LIKE %s
                OR p.gender_optional LIKE %s
                OR d.department_name LIKE %s
                OR v.visit_type LIKE %s
            )
        """
        params.extend([search] * 7)

    if filters.get("department_id"):
        query += " AND v.department_id = %s"
        params.append(filters["department_id"])

    if filters.get("visit_type"):
        query += " AND v.visit_type = %s"
        params.append(filters["visit_type"])

    if filters.get("start_date"):
        query += " AND v.visit_date >= %s"
        params.append(filters["start_date"])

    if filters.get("end_date"):
        query += " AND v.visit_date <= %s"
        params.append(filters["end_date"])

    query += " ORDER BY v.visit_date DESC, v.visit_id DESC"

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, params)
        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def add_visit(age, gender, department_id, visit_date, visit_type,
              patient_name=""):
    patient_name = patient_name.strip()

    if not patient_name:
        raise ValueError("Patient name is required.")

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO patients
                (patient_name, age, gender_optional)
            VALUES (%s, %s, %s)
        """, (patient_name, age, gender))

        patient_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO visits
                (patient_id, department_id, visit_date, visit_type)
            VALUES (%s, %s, %s, %s)
        """, (patient_id, department_id, visit_date, visit_type))

        connection.commit()
        return patient_id

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def get_visit(visit_id):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                v.visit_id,
                v.patient_id,
                p.patient_name,
                p.age,
                p.gender_optional AS gender,
                v.department_id,
                v.visit_date,
                v.visit_type
            FROM visits v
            JOIN patients p ON v.patient_id = p.patient_id
            WHERE v.visit_id = %s
        """, (visit_id,))

        return cursor.fetchone()

    finally:
        cursor.close()
        connection.close()


def update_visit(
    visit_id, patient_id, age, gender,
    department_id, visit_date, visit_type,
    patient_name=None
):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        if patient_name is not None:
            cursor.execute("""
                UPDATE patients
                SET patient_name = %s,
                    age = %s,
                    gender_optional = %s
                WHERE patient_id = %s
            """, (patient_name.strip(), age, gender, patient_id))
        else:
            cursor.execute("""
                UPDATE patients
                SET age = %s, gender_optional = %s
                WHERE patient_id = %s
            """, (age, gender, patient_id))

        cursor.execute("""
            UPDATE visits
            SET department_id = %s,
                visit_date = %s,
                visit_type = %s
            WHERE visit_id = %s
        """, (department_id, visit_date, visit_type, visit_id))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def delete_visit(visit_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT patient_id FROM visits WHERE visit_id = %s",
            (visit_id,)
        )
        result = cursor.fetchone()

        if result:
            patient_id = result[0]

            cursor.execute(
                "DELETE FROM visits WHERE visit_id = %s",
                (visit_id,)
            )

            cursor.execute(
                "SELECT COUNT(*) FROM visits WHERE patient_id = %s",
                (patient_id,)
            )

            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "DELETE FROM patients WHERE patient_id = %s",
                    (patient_id,)
                )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
