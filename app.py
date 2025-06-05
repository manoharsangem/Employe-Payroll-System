from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'payroll_secret_key'

# Database setup
def init_db():
    conn = sqlite3.connect('payroll.db')
    cursor = conn.cursor()
    
    # Create employees table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        position TEXT NOT NULL,
        joining_date TEXT NOT NULL,
        base_salary REAL NOT NULL
    )
    ''')
    
    # Create salary_records table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS salary_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        month TEXT NOT NULL,
        year INTEGER NOT NULL,
        base_salary REAL NOT NULL,
        overtime_hours REAL DEFAULT 0,
        overtime_rate REAL DEFAULT 0,
        bonus REAL DEFAULT 0,
        deductions REAL DEFAULT 0,
        net_salary REAL NOT NULL,
        payment_date TEXT,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (employee_id) REFERENCES employees (id)
    )
    ''')
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    ''')
    
    # Insert default admin user if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                      ('admin', 'admin123', 'admin'))
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('payroll.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/employees')
def employees():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('payroll.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees ORDER BY name")
    employees = cursor.fetchall()
    conn.close()
    
    return render_template('employees.html', employees=employees)

@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        position = request.form['position']
        joining_date = request.form['joining_date']
        base_salary = request.form['base_salary']
        
        conn = sqlite3.connect('payroll.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO employees (name, email, position, joining_date, base_salary) VALUES (?, ?, ?, ?, ?)",
                (name, email, position, joining_date, base_salary)
            )
            conn.commit()
            flash('Employee added successfully!', 'success')
            return redirect(url_for('employees'))
        except sqlite3.IntegrityError:
            flash('Email already exists!', 'error')
        finally:
            conn.close()
    
    return render_template('add_employee.html')

@app.route('/edit_employee/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('payroll.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        position = request.form['position']
        joining_date = request.form['joining_date']
        base_salary = request.form['base_salary']
        
        try:
            cursor.execute(
                "UPDATE employees SET name = ?, email = ?, position = ?, joining_date = ?, base_salary = ? WHERE id = ?",
                (name, email, position, joining_date, base_salary, id)
            )
            conn.commit()
            flash('Employee updated successfully!', 'success')
            return redirect(url_for('employees'))
        except sqlite3.IntegrityError:
            flash('Email already exists!', 'error')
        finally:
            conn.close()
    
    cursor.execute("SELECT * FROM employees WHERE id = ?", (id,))
    employee = cursor.fetchone()
    conn.close()
    
    return render_template('edit_employee.html', employee=employee)

@app.route('/delete_employee/<int:id>')
def delete_employee(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('payroll.db')
    cursor = conn.cursor()
    
    try:
        # Check if employee has salary records
        cursor.execute("SELECT COUNT(*) FROM salary_records WHERE employee_id = ?", (id,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            flash('Cannot delete employee with salary records!', 'error')
        else:
            cursor.execute("DELETE FROM employees WHERE id = ?", (id,))
            conn.commit()
            flash('Employee deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('employees'))

@app.route('/payroll')
def payroll():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    month = request.args.get('month', datetime.now().strftime('%m'))
    year = request.args.get('year', datetime.now().strftime('%Y'))
    
    conn = sqlite3.connect('payroll.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all salary records for the selected month and year
    cursor.execute("""
        SELECT sr.*, e.name, e.position 
        FROM salary_records sr
        JOIN employees e ON sr.employee_id = e.id
        WHERE sr.month = ? AND sr.year = ?
        ORDER BY e.name
    """, (month, year))
    
    salary_records = cursor.fetchall()
    
    # Get employees without salary records for the selected month and year
    cursor.execute("""
        SELECT e.* 
        FROM employees e
        WHERE e.id NOT IN (
            SELECT sr.employee_id 
            FROM salary_records sr 
            WHERE sr.month = ? AND sr.year = ?
        )
        ORDER BY e.name
    """, (month, year))
    
    employees_without_records = cursor.fetchall()
    
    conn.close()
    
    return render_template('payroll.html', 
                          salary_records=salary_records, 
                          employees_without_records=employees_without_records,
                          selected_month=month,
                          selected_year=year)

@app.route('/generate_salary/<int:id>', methods=['GET', 'POST'])
def generate_salary(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('payroll.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if request.method == 'POST':
        month = request.form['month']
        year = request.form['year']
        base_salary = float(request.form['base_salary'])
        overtime_hours = float(request.form.get('overtime_hours', 0))
        overtime_rate = float(request.form.get('overtime_rate', 0))
        bonus = float(request.form.get('bonus', 0))
        deductions = float(request.form.get('deductions', 0))
        
        # Calculate net salary
        net_salary = base_salary + (overtime_hours * overtime_rate) + bonus - deductions
        
        # Check if record already exists
        cursor.execute("""
            SELECT id FROM salary_records 
            WHERE employee_id = ? AND month = ? AND year = ?
        """, (id, month, year))
        
        existing_record = cursor.fetchone()
        
        if existing_record:
            cursor.execute("""
                UPDATE salary_records 
                SET base_salary = ?, overtime_hours = ?, overtime_rate = ?, 
                    bonus = ?, deductions = ?, net_salary = ?
                WHERE id = ?
            """, (base_salary, overtime_hours, overtime_rate, bonus, deductions, net_salary, existing_record['id']))
            flash('Salary record updated successfully!', 'success')
        else:
            cursor.execute("""
                INSERT INTO salary_records 
                (employee_id, month, year, base_salary, overtime_hours, overtime_rate, 
                bonus, deductions, net_salary, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (id, month, year, base_salary, overtime_hours, overtime_rate, 
                bonus, deductions, net_salary, 'pending'))
            flash('Salary record created successfully!', 'success')
        
        conn.commit()
        return redirect(url_for('payroll', month=month, year=year))
    
    cursor.execute("SELECT * FROM employees WHERE id = ?", (id,))
    employee = cursor.fetchone()
    
    month = request.args.get('month', datetime.now().strftime('%m'))
    year = request.args.get('year', datetime.now().strftime('%Y'))
    
    # Check if salary record exists
    cursor.execute("""
        SELECT * FROM salary_records 
        WHERE employee_id = ? AND month = ? AND year = ?
    """, (id, month, year))
    
    salary_record = cursor.fetchone()
    
    conn.close()
    
    return render_template('generate_salary.html', 
                          employee=employee, 
                          salary_record=salary_record,
                          month=month,
                          year=year)

@app.route('/process_payment/<int:id>', methods=['POST'])
def process_payment(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('payroll.db')
    cursor = conn.cursor()
    
    payment_date = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute("""
        UPDATE salary_records 
        SET status = 'paid', payment_date = ?
        WHERE id = ?
    """, (payment_date, id))
    
    conn.commit()
    conn.close()
    
    flash('Payment processed successfully!', 'success')
    return redirect(url_for('payroll'))

@app.route('/salary_slip/<int:id>')
def salary_slip(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('payroll.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT sr.*, e.name, e.email, e.position, e.joining_date
        FROM salary_records sr
        JOIN employees e ON sr.employee_id = e.id
        WHERE sr.id = ?
    """, (id,))
    
    salary_record = cursor.fetchone()
    conn.close()
    
    if not salary_record:
        flash('Salary record not found!', 'error')
        return redirect(url_for('payroll'))
    
    return render_template('salary_slip.html', record=salary_record)

if __name__ == '__main__':
    app.run(debug=True)