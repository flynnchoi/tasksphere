from flask import Flask, redirect, url_for, render_template, request, session, g, make_response, flash, jsonify
from models import db
from models.user import User
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from flask_migrate import Migrate
from models.task import Task
from datetime import datetime
from models.meeting import Meeting
from models.category import Category
from models.department import Department
from models.project import Project
import os
from sqlalchemy import case, func, cast
from sqlalchemy.types import String
import calendar
import pytz
from markupsafe import Markup
from flask_wtf.csrf import CSRFProtect, CSRFError

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY'),
    SQLALCHEMY_DATABASE_URI='sqlite:///tasksphere.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=15)
)
csrf = CSRFProtect(app)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

migrate = Migrate(app, db)

# Comment out this block temporarily
with app.app_context():
    db.create_all()
    
    # Create default categories if they don't exist
    default_categories = ['Work', 'Personal', 'Urgent', 'Long-term']
    for cat_name in default_categories:
        if not Category.query.filter_by(name=cat_name).first():
            category = Category(name=cat_name)
            db.session.add(category)
    
    # Create default departments if they don't exist
    default_departments = ['Engineering', 'Marketing', 'Sales', 'HR', 'Operations', 'Finance']
    for dept_name in default_departments:
        if not Department.query.filter_by(name=dept_name).first():
            department = Department(name=dept_name)
            db.session.add(department)
    
    db.session.commit()

# User loader callback
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Ensure session is permanent for timeout
@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('login.html')
            
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# Protected route example
@app.route('/dashboard')
@login_required
def dashboard():
    # Set the timezone
    tz = pytz.timezone('Asia/Seoul')  # Replace with your timezone

    # Get the current time with timezone
    now = datetime.now(tz)

    # Fetch tasks for the current user with due dates in the future
    user_tasks = Task.query.filter_by(user_id=current_user.id)\
        .filter(Task.due_date >= now)\
        .order_by(
            case(
                (Task.priority == 'High', 1),
                (Task.priority == 'Medium', 2),
                (Task.priority == 'Low', 3)
            ),
            Task.due_date
        ).all()
    
    # Fetch all upcoming meetings for today and future
    user_meetings = Meeting.query.filter_by(user_id=current_user.id)\
        .filter(Meeting.date_time >= now)\
        .order_by(Meeting.date_time).all()

    # Fetch meetings within the next 24 hours and 1 hour
    upcoming_24h = Meeting.query.filter_by(user_id=current_user.id)\
        .filter(Meeting.date_time >= now, Meeting.date_time <= now + timedelta(hours=24))\
        .order_by(Meeting.date_time).all()

    upcoming_1h = Meeting.query.filter_by(user_id=current_user.id)\
        .filter(Meeting.date_time >= now, Meeting.date_time <= now + timedelta(hours=1))\
        .order_by(Meeting.date_time).all()

    # Serialize meetings to make them JSON serializable
    def serialize_meeting(meeting):
        return {
            'id': meeting.id,
            'title': meeting.title,
            'date_time': meeting.date_time.strftime('%Y-%m-%dT%H:%M:%S%z'),  # ISO format with timezone
            'location': meeting.location,
            'user_id': meeting.user_id,
            'duration': meeting.duration
        }

    upcoming_meetings_serialized = [serialize_meeting(meeting) for meeting in user_meetings]

    return render_template(
        'dashboard.html',
        tasks=user_tasks,
        meetings=user_meetings,
        upcoming_meetings=upcoming_meetings_serialized
    )

def get_db():
    if 'db' not in g:
        g.db = db
    return g.db

@app.teardown_appcontext
def teardown_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.session.close()

def init_db():
    db.create_all()

@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    init_db()
    print('Initialized the database.')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            return 'Username already exists'
        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/tasks')
@login_required
def tasks():
    user_tasks = Task.query.filter_by(user_id=current_user.id)\
        .order_by(
            case(
                (Task.priority == 'High', 1),
                (Task.priority == 'Medium', 2),
                (Task.priority == 'Low', 3)
            ),
            Task.due_date
        ).all()
    return render_template('tasks.html', tasks=user_tasks)

@app.route('/add_task', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        due_date = request.form['due_date']
        
        # Validate the date
        try:
            # Parse the date
            due_datetime = datetime.strptime(due_date, '%Y-%m-%d')
            
            # Verify it's not in the past
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if due_datetime < today:
                flash('Please select a future date.', 'error')
                return redirect(url_for('add_task'))
            
            # Verify it's not too far in the future (e.g., 2 years)
            max_date = today.replace(year=today.year + 2)
            if due_datetime > max_date:
                flash('Due date cannot be more than 2 years in the future.', 'error')
                return redirect(url_for('add_task'))
            
        except ValueError:
            flash('Invalid date format or date does not exist.', 'error')
            return redirect(url_for('add_task'))
        
        priority = request.form['priority']
        department_id = request.form.get('department_id')
        project_id = request.form.get('project_id')
        category_ids = request.form.getlist('categories[]')
        
        new_task = Task(
            title=title,
            description=description,
            due_date=due_datetime,
            priority=priority,
            department_id=department_id if department_id else None,
            project_id=project_id if project_id else None,
            user_id=current_user.id
        )
        
        # Add selected categories
        if category_ids:
            categories = Category.query.filter(Category.id.in_(category_ids)).all()
            new_task.categories.extend(categories)
        
        db.session.add(new_task)
        db.session.commit()
        return redirect(url_for('tasks'))
        
    # GET request - show form
    departments = Department.query.all()
    projects = Project.query.all()
    categories = Category.query.all()
    return render_template('add_task.html', 
                         departments=departments,
                         projects=projects,
                         categories=categories)

@app.route('/meetings')
@login_required
def meetings():
    user_meetings = Meeting.query.filter_by(user_id=current_user.id).order_by(Meeting.date_time).all()
    return render_template('meetings.html', meetings=user_meetings)

@app.route('/add_meeting', methods=['GET', 'POST'])
@login_required
def add_meeting():
    if request.method == 'POST':
        title = request.form['title']
        meeting_date = request.form['meeting_date']
        meeting_time = request.form['meeting_time']
        location = request.form['location']
        duration = int(request.form['duration'])
        
        try:
            date_time = datetime.strptime(f"{meeting_date} {meeting_time}", '%Y-%m-%d %H:%M')
            end_time = date_time + timedelta(minutes=duration)

            # Use printf to construct the modifier string
            duration_modifier = func.printf('+%s minutes', cast(Meeting.duration, String))

            # Check for overlapping meetings
            conflicting_meeting = Meeting.query.filter(
                Meeting.user_id == current_user.id,
                Meeting.date_time < end_time,
                func.datetime(Meeting.date_time, duration_modifier) > date_time
            ).first()

            if conflicting_meeting:
                flash('Meeting time conflicts with another scheduled meeting.', 'error')
                return render_template('add_meeting.html', conflicting_meeting=conflicting_meeting, form_data=request.form)

            # Proceed to add the new meeting if no conflicts
            new_meeting = Meeting(
                title=title,
                date_time=date_time,
                location=location,
                user_id=current_user.id,
                duration=duration
            )
            db.session.add(new_meeting)
            db.session.commit()
            flash('Meeting scheduled successfully!', 'success')
            return redirect(url_for('meetings'))

        except ValueError:
            flash('Invalid date/time format.', 'error')
            return redirect(url_for('add_meeting'))
    
    return render_template('add_meeting.html')

@app.before_request
def before_request():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=15)

@app.after_request
def after_request(response):
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/search_tasks', methods=['GET', 'POST'])
@login_required
def search_tasks():
    if request.method == 'POST':
        keyword = request.form['keyword']
        results = Task.query.filter(
            Task.user_id == current_user.id,
            Task.title.contains(keyword)
        ).all()
        return render_template('search_results.html', tasks=results)
    return render_template('search_tasks.html')

@app.route('/projects')
@login_required
def projects():
    # Clear any existing flash messages before showing projects page
    session.pop('_flashes', None)
    all_projects = Project.query.all()
    return render_template('projects.html', projects=all_projects)

@app.route('/add_project', methods=['GET', 'POST'])
@login_required
def add_project():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        department_id = request.form.get('department_id')
        
        # Check if project name already exists
        if Project.query.filter_by(name=name).first():
            flash('A project with this name already exists.', 'error')
            return redirect(url_for('add_project'))
        
        new_project = Project(
            name=name,
            description=description,
            department_id=department_id if department_id else None
        )
        
        db.session.add(new_project)
        db.session.commit()
        flash('Project created successfully!', 'success')
        return redirect(url_for('projects'))
        
    departments = Department.query.all()
    return render_template('add_project.html', departments=departments)

@app.route('/edit_project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'POST':
        name = request.form['name']
        
        # Check if another project already has this name
        existing_project = Project.query.filter_by(name=name).first()
        if existing_project and existing_project.id != project_id:
            flash('A project with this name already exists.', 'error')
            return redirect(url_for('edit_project', project_id=project_id))
            
        project.name = name
        project.description = request.form['description']
        project.department_id = request.form.get('department_id')
        
        db.session.commit()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('projects'))
        
    departments = Department.query.all()
    return render_template('edit_project.html', project=project, departments=departments)

@app.route('/delete_project/<int:project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check if there are any tasks associated with this project
    if Task.query.filter_by(project_id=project_id).first():
        flash('Cannot delete project with associated tasks.', 'error')
        return redirect(url_for('projects'))
    
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted successfully!', 'success')
    return redirect(url_for('projects'))

# Add CSRF error handler
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return jsonify({'error': 'CSRF token is missing or invalid'}), 400

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    if request.method == 'POST':
        keyword = request.form.get('keyword', '').strip()
        search_type = request.form.get('search_type', 'both')

        tasks = []
        meetings = []

        if search_type in ('tasks', 'both'):
            tasks = Task.query.filter(
                Task.user_id == current_user.id,
                Task.title.ilike(f'%{keyword}%') | Task.description.ilike(f'%{keyword}%')
            ).order_by(Task.due_date).all()

        if search_type in ('meetings', 'both'):
            meetings = Meeting.query.filter(
                Meeting.user_id == current_user.id,
                Meeting.title.ilike(f'%{keyword}%') | Meeting.location.ilike(f'%{keyword}%')
            ).order_by(Meeting.date_time).all()

        return render_template(
            'search.html',
            keyword=keyword,
            search_type=search_type,
            tasks=tasks,
            meetings=meetings
        )
    else:
        return render_template('search.html')

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        # Set the timezone
        tz = pytz.timezone('Asia/Seoul')  # Replace with your timezone
        now = datetime.now(tz)

        # Fetch meetings within the next 24 hours and 1 hour
        upcoming_24h = Meeting.query.filter_by(user_id=current_user.id)\
            .filter(Meeting.date_time >= now, Meeting.date_time <= now + timedelta(hours=24))\
            .order_by(Meeting.date_time).all()

        upcoming_1h = Meeting.query.filter_by(user_id=current_user.id)\
            .filter(Meeting.date_time >= now, Meeting.date_time <= now + timedelta(hours=1))\
            .order_by(Meeting.date_time).all()

        notifications = []

        # Notifications for meetings in the next hour
        for meeting in upcoming_1h:
            notifications.append(Markup(f"""
                <div class="notification-time text-muted mb-1" style="font-size: 0.8rem;">
                    <i class="fas fa-clock mr-1"></i>Starting in less than 1 hour
                </div>
                <div class="notification-title mb-1" style="font-weight: 600; color: #dc3545;">
                    {meeting.title}
                </div>
                <div class="notification-details" style="font-size: 0.9rem;">
                    <i class="fas fa-calendar-alt mr-1"></i>{meeting.date_time.strftime('%Y-%m-%d %H:%M')}
                    {f'<br><i class="fas fa-map-marker-alt mr-1"></i>{meeting.location}' if meeting.location else ''}
                </div>
            """))

        # Notifications for meetings in the next 24 hours (excluding those in next hour)
        for meeting in upcoming_24h:
            if meeting not in upcoming_1h:
                notifications.append(Markup(f"""
                    <div class="notification-time text-muted mb-1" style="font-size: 0.8rem;">
                        <i class="fas fa-clock mr-1"></i>Within 24 hours
                    </div>
                    <div class="notification-title mb-1" style="font-weight: 600; color: #ffc107;">
                        {meeting.title}
                    </div>
                    <div class="notification-details" style="font-size: 0.9rem;">
                        <i class="fas fa-calendar-alt mr-1"></i>{meeting.date_time.strftime('%Y-%m-%d %H:%M')}
                        {f'<br><i class="fas fa-map-marker-alt mr-1"></i>{meeting.location}' if meeting.location else ''}
                    </div>
                """))

        return dict(notifications=notifications)
    else:
        return dict(notifications=[])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # Create a test user if one doesn't exist
        if not User.query.filter_by(username='testuser').first():
            hashed_password = generate_password_hash('testpassword')
            new_user = User(username='testuser', password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            print('Test user created: testuser / testpassword')
    app.run(debug=True)