from flask import Flask, render_template, request,redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_wtf import FlaskForm
from flask_socketio import SocketIO, emit, join_room, leave_room
from dotenv import load_dotenv
import os
import random
import pandas as pd
import pdfkit
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime
from flask_report import Report


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz.db'
db = SQLAlchemy(app)

#models

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    quizzes = db.relationship('Quiz', backref='author', lazy=True)

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    no_of_questions = db.relationship('Question', backref='quiz', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    option1 = db.Column(db.String(50), nullable=False)
    option2 = db.Column(db.String(50), nullable=False)
    option3 = db.Column(db.String(50), nullable=False)
    option4 = db.Column(db.String(50), nullable=False)
    answer = db.Column(db.String(50), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    creator = db.relationship('User', backref=db.backref('groups', lazy=True))
    members = db.relationship('User', secondary='user_group', backref=db.backref('groups_joined', lazy=True))


user_group = db.Table('user_group',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id'), primary_key=True)
)


#auth

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        return redirect(request.args.get('next') or url_for('index'))
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created', 'success')
        return redirect('/login')
    return render_template('register.html')

#quiz management 

@app.route("/create_quiz", methods=["GET", "POST"])
def create_quiz():
    if request.method == "POST":
        quiz_name = request.form["quiz_name"]
        code=random.choice(string.ascii_lowercase) for _ in range(length)
        userid=request.form["username"]
        no_of_questions=int(request.form["no_of_questions"])
        questions = []
        for i in range(1, no_of_questions):
            question = request.form[f"question_{i}"]
            answers = [request.form[f"question_{i}answer{j}"] for j in range(1, no_of_questions)]
            correct_answer = request.form[f"question_{i}_correct_answer"]           
            questions = [Question(question=q["question"], answer=q["answer"]) for q in data["questions"]]
            return redirect(url_for("quiz", quiz_id=quiz_id))
    quiz_name.questions = questions
    # Add the quiz to the database
    db.session.add(quiz_name)
    db.session.commit()
    return render_template("create_quiz.html")

@app.route("/join_quiz")
def join_quiz():
    return render_template("join_quiz.html", quizzes=quizzes)

@app.route("/quiz/<int:quiz_id>")
def quiz(quiz_id):
    # Get the quiz with the given ID
    quiz = quizzes[quiz_id]
    # Get the current question index from the query parameters
    current_question = request.args.get("q", default=0, type=int)
    # If the quiz is finished, redirect to the results page
    if current_question == len(quiz["questions"]):
        return redirect(url_for("quiz_results", quiz_id=quiz_id))
    # Get the current question from the quiz
    question = quiz["questions"][current_question]
    return render_template("quiz.html", quiz=quiz, question=question, current_question=current_question)

# Define a route for the quiz results page
@app.route("/quiz/<int:quiz_id>/results")
def quiz_results(quiz_id):
    # Get the quiz with the given ID
    quiz = quizzes[quiz_id]
    # Get the number of correct answers
    num_correct = 0
    for question in quiz["questions"]:
        if request.args.get(question["question"]) == question["answer"]:
            num_correct += 1
    # Render the results page with the number of correct answers
    return render_template("quiz_results.html", quiz=quiz, num)


# SocketIO event handler for starting a quiz
@socketio.on('start_quiz')
def handle_start_quiz(data):
    room_id = session.get('room_id')
    if room_id is None:
        emit('quiz_error', {'message': 'You must join a quiz first'})
    else:
        room = Room.query.filter_by(id=room_id).first()
        if room.quiz_started:
            emit('quiz_error', {'message': 'Quiz has already been started'})
        else:
            random.shuffle(quiz_questions)
            room.quiz_started = True
            room.quiz_question_index = 0
            db.session.commit()
            emit('quiz_started', {'questions': quiz_questions}, room=room.invitation_code)

# SocketIO event handler for answering a quiz question
@socketio.on('answer_question')
def handle_answer_question(data):
    room_id = session.get('room_id')
    if room_id is None:
        emit('quiz_error', {'message': 'You must join a quiz first'})
    else:
        room = Room.query.filter_by(id=room_id).first()
        if not room.quiz_started:
            emit('quiz_error', {'message': 'Quiz has not been started yet'})
        else:
            username = session.get('username')
            user = User.query.filter_by(username=username, room_id=room.id).first()
            if user is None:
                emit('quiz_error', {'message': 'Invalid user'})
            else:
                question_index = room.quiz_question_index
                if question_index >= len(quiz_questions):
                    emit('quiz_error', {'message': 'Quiz has already ended'})
                else:
                    question = quiz_questions[question_index]
                    answer_text = data.get('answer', '').strip().lower()
                    answer_correct = answer_text == question['answer'].lower()
                    answer = Answer(question_id=question['id'], user=user, room=room)
                    db.session.add(answer)
                    db.session.commit()
                    emit('answer_result', {'correct': answer_correct, 'answer': question['answer']}, room=room.invitation_code)
                    if answer_correct:
                        room.quiz_question_index += 1
                        db.session.commit()
                    emit('next_question', {'index': room.quiz_question_index, 'question': quiz_questions[room.quiz_question_index]}, room=room.invitation_code)

#group management
    
@app.route('/groups', methods=['GET', 'POST'])
def groups():
    if request.method == 'POST':
        group_name = request.form['group_name']
        user_name = request.form['user_name']
        # add the user to the group in the database
        return redirect(url_for('groups'))
    # get the list of groups and their members from the database
    return render_template('groups.html', groups=groups)

@app.route('/groups/new', methods=['GET', 'POST'])
def new_group():
    if request.method == 'POST':
        # Add the new group to the database
        name = request.form['name']
        description = request.form['description']
        creater=request.form['username']
        return redirect(url_for('groups'))
    else:
        return render_template('new_group.html')

    
@app.route('/group/join-quiz', methods=['GET', 'POST'])
def join_group_quiz():
    if request.method == 'POST':
        code = request.form['code']
        if code not in quizzes:
            flash('Invalid invitation code')
            return redirect(url_for('join_quiz'))
        group_name = request.form['group_name']
        player_name = request.form['player_name']
        if group_name not in groups:
            groups[group_name] = {'players': [player_name], 'quiz_code': code}
        else:
            groups[group_name]['players'].append(player_name)
            groups[group_name]['quiz_code'] = code
        return redirect(url_for('play_quiz', group_name=group_name, player_name=player_name))
    return render_template('join_group_quiz.html')

# A route to play a quiz
@app.route('/play-quiz/<group_name>/<player_name>', methods=['GET', 'POST'])
def play_quiz(group_name, player_name):
    if request.method == 'POST':
        quiz_code = groups[group_name]['quiz_code']
        quiz = quizzes[quiz_code]
        questions = quiz['questions']
        user_answer = request.form['answer']
        question_index = int(request.form['question_index'])
        correct_answer = questions[question_index]['answer']
        if user_answer == correct_answer:
            if player_name not in users:
                users[player_name] = {'score': 1, 'group': group_name}
            else:
                users[player_name]['score'] += 1
        return redirect(url_for('play_quiz', group_name=group_name, player_name=player_name))
    quiz_code = groups[group_name]['quiz_code']
    quiz = quizzes[quiz_code]
    questions = quiz['questions']
    question_index = random.randint(0, 4)
    question = questions[question_index]['question']
    options = questions[question_index




# Socket event to add a user to a team
@socketio.on('join_team')
def join_team(data):
    username = data['username']
    invitation_code = data['invitation_code']
    team_name = data['team_name']
    if team_name not in users:
        users[team_name] = []
    users[team_name].append(username)
    emit('team_joined', {'team_name': team_name}, broadcast=True)

# Socket event to get the current quiz question
@socketio.on('get_question')
def get_question(data):
    invitation_code = data['invitation_code']
    quiz = next((q for q in quizzes if q['code'] == invitation_code), None)
    if quiz:
        current_question_index = quiz['current_question_index']
        if current_question_index < len(quiz['questions']):
            question = quiz['questions'][current_question_index]
            emit('question', {'question': question}, broadcast=True)
        else:
            emit('quiz_end', broadcast=True)

# SocketIO events
@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    emit('joined', {'username': username, 'room': room}, room=room)

@socketio.on('answer')
def on_answer(data):
    username = data['username']
    room = data['room']
    answer = data['answer']
    # Process answer and emit results
    emit('results', {'username': username, 'room': room, 'answer': answer}, room=room)


#export

@app.route("/quiz/<int:quiz_id>/export/pdf")
def export_pdf():
    if request.method == 'POST':
        # Retrieve the questions and answers from the database
        questions = []
        answers = []
        for row in c.execute('SELECT * FROM quiz'):
            questions.append(row[0])
            answers.append(row[1])

        # Create a list of tuples containing the question and its corresponding answer
        quiz = list(zip(questions, answers))

        # Create a PDF file with the quiz
        pdfkit.from_string(render_template('quiz.html', quiz=quiz), 'quiz.pdf')

        # Return the PDF file as a response
        response = make_response(open('quiz.pdf', 'rb').read())
        response.headers.set('Content-Type', 'application/pdf')
        response.headers.set('Content-Disposition', 'attachment', filename='quiz.pdf')
        return response
    return render_template('export.html')

# Define a route for exporting a quiz as a Google Form
@app.route("/quiz/<int:quiz_id>/export/form")
def export_quiz_form(quiz_id):
    quiz = Quiz.query.get(quiz_id)
    if quiz is None:
        return jsonify({"error": "Quiz not found"})
    # Build the Google Form URL
    form_url = "https://docs.google.com/forms/d/e/{form_id}/viewform?usp=pp_url&entry.{field_id}={field_value}"
    form_id = "{your_google_form_id}"
    field_id_question = "{your_question_field_id}"
    field_id_answer = "{your_answer_field_id}"
    # Build the quiz questions and answers
    quiz_data = {}
    for i, question in enumerate(quiz.questions):
        quiz_data[f"Question {i+1}"] = question.question
        quiz_data[f"Answer {i+1}"] = question.answer
    # Build the form entries
    entries = []
    for key, value in quiz_data.items():
        entries.append({
            "field_id": field_id_question,
            "field_value": key
        })
        entries.append({
            "field_id": field_id_answer,
            "field_value": value
        })
    # Build the form URL with the entries
    form_url = form_url.format(form_id=form_id, field_id=entries[0]["field_id"], field_value=entries[0]["field_value"])
    for entry in entries[1:]:
        form_url += f"&entry.{entry['field_id']}={entry['field_value']}"
    # Redirect to the Google Form URL
    return redirect(form_url)
    return render_template('export.html')
