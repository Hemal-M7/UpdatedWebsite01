from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Appointment, Message, Availability, MedicalRecord
from datetime import datetime, timedelta

# Initialize app and extensions
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SECRET_KEY'] = 'your_secret_key'

db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        role = request.form['role']
        specialization = request.form.get('specialization') if role == 'doctor' else None
        user = User(username=username, password=password, role=role, specialization=specialization)
        db.session.add(user)
        db.session.commit()
        flash('Account created successfully!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and bcrypt.check_password_hash(user.password, request.form['password']):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check your credentials.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'doctor':
        appointments = Appointment.query.filter_by(doctor_id=current_user.id).all()
        availability = Availability.query.filter_by(doctor_id=current_user.id).all()
        return render_template('doctor_dashboard.html', appointments=appointments, availability=availability)
    elif current_user.role == 'patient':
        appointments = Appointment.query.filter_by(patient_id=current_user.id).all()
        medical_records = MedicalRecord.query.filter_by(patient_id=current_user.id).all()
        return render_template('patient_dashboard.html', appointments=appointments, medical_records=medical_records)
    else:
        flash('Invalid role.', 'danger')
        return redirect(url_for('logout'))

@app.route('/set_availability', methods=['GET', 'POST'])
@login_required
def set_availability():
    if current_user.role != 'doctor':
        flash('Only doctors can set availability.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            date_time_start = datetime.strptime(request.form['date_time_start'], '%Y-%m-%dT%H:%M')
            date_time_end = datetime.strptime(request.form['date_time_end'], '%Y-%m-%dT%H:%M')

            if date_time_end <= date_time_start:
                flash('End time must be later than start time.', 'danger')
                return redirect(url_for('set_availability'))

            availability = Availability(doctor_id=current_user.id, date_time_start=date_time_start, date_time_end=date_time_end)
            db.session.add(availability)
            db.session.commit()
            flash('Availability added successfully!', 'success')
            return redirect(url_for('dashboard'))
        except ValueError:
            flash('Invalid date/time format.', 'danger')

    return render_template('set_availability.html')

@app.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    if current_user.role != 'patient':
        flash('Only patients can book appointments.', 'danger')
        return redirect(url_for('dashboard'))

    doctors = User.query.filter_by(role='doctor').all()
    available_slots = []

    doctor_id = request.args.get('doctor_id')
    if doctor_id:
        # Fetch available time slots for the selected doctor
        availability = Availability.query.filter_by(doctor_id=doctor_id).filter(
            Availability.date_time_start >= datetime.utcnow()
        ).all()

        for availability_item in availability:
            current_time = availability_item.date_time_start
            while current_time + timedelta(hours=1) <= availability_item.date_time_end:
                available_slots.append({
                    'start': current_time,
                    'end': current_time + timedelta(hours=1)
                })
                current_time += timedelta(hours=1)

    if request.method == 'POST':
        date_time = request.form.get('date_time')
        try:
            date_time_obj = datetime.strptime(date_time, '%Y-%m-%dT%H:%M')

            # Ensure the selected time slot is valid
            availability = Availability.query.filter_by(doctor_id=doctor_id).filter(
                Availability.date_time_start <= date_time_obj,
                Availability.date_time_end >= date_time_obj
            ).first()

            if not availability:
                flash('The selected time slot is not available. Please choose a different time.', 'danger')
                return redirect(url_for('book', doctor_id=doctor_id))

            # Create the appointment
            appointment = Appointment(
                date_time=date_time_obj,
                doctor_id=int(doctor_id),
                patient_id=current_user.id
            )
            db.session.add(appointment)
            db.session.commit()
            flash('Appointment booked successfully!', 'success')
            return redirect(url_for('dashboard'))
        except ValueError:
            flash('Invalid date/time format.', 'danger')

    return render_template('book_doctor.html', doctors=doctors, available_slots=available_slots)

@app.route('/chat/<int:receiver_id>', methods=['GET', 'POST'])
@login_required
def chat(receiver_id):
    receiver = User.query.get_or_404(receiver_id)
    if request.method == 'POST':
        content = request.form['content']
        message = Message(sender_id=current_user.id, receiver_id=receiver.id, content=content)
        db.session.add(message)
        db.session.commit()
        flash('Message sent!', 'success')
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == receiver.id)) |
        ((Message.sender_id == receiver.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp).all()
    return render_template('messages.html', receiver=receiver, messages=messages)

@app.route('/reminders')
@login_required
def reminders():
    if current_user.role == 'patient':
        upcoming_appointments = Appointment.query.filter_by(patient_id=current_user.id).filter(
            Appointment.date_time > datetime.utcnow()
        ).all()
        return render_template('reminders.html', appointments=upcoming_appointments)
    flash('Reminders are available for patients only.', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/medical_records/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def edit_medical_records(patient_id):
    if current_user.role != 'doctor':
        flash('Only doctors can edit medical records.', 'danger')
        return redirect(url_for('dashboard'))

    patient = User.query.get_or_404(patient_id)

    # Retrieve the patient's medical record
    record = MedicalRecord.query.filter_by(patient_id=patient.id).first()

    if request.method == 'POST':
        diagnosis = request.form['diagnosis']
        treatment_plan = request.form.get('treatment_plan')
        notes = request.form.get('notes')

        # Create or update a medical record
        if record is None:
            record = MedicalRecord(
                patient_id=patient.id,
                doctor_id=current_user.id,
                diagnosis=diagnosis,
                treatment_plan=treatment_plan,
                notes=notes
            )
            db.session.add(record)
        else:
            record.diagnosis = diagnosis
            record.treatment_plan = treatment_plan
            record.notes = notes
            record.updated_at = datetime.utcnow()

        db.session.commit()
        flash('Medical record updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('edit_medical_records.html', patient=patient, record=record)

@app.route('/medical_records', methods=['GET'])
@login_required
def view_medical_records():
    if current_user.role != 'patient':
        flash('Only patients can view medical records.', 'danger')
        return redirect(url_for('dashboard'))

    records = MedicalRecord.query.filter_by(patient_id=current_user.id).all()
    return render_template('view_medical_records.html', records=records)

@app.template_filter('datetimeformat')
def datetimeformat(value, format='%I:%M %p'):
    """Custom Jinja filter to format datetime objects."""
    return value.strftime(format)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)