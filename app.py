import os
import bcrypt
from flask import Flask, render_template, request, redirect, url_for, session, make_response, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change this for production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data/polls.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize DB
db = SQLAlchemy(app)

# --- Models ---
class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    options = db.relationship('Option', backref='poll', lazy=True, cascade="all, delete-orphan")

    def total_votes(self):
        return sum(option.votes for option in self.options)

class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    text = db.Column(db.String(100), nullable=False)
    votes = db.Column(db.Integer, default=0)

# --- Auth ---
# Hardcoded admin credentials
ADMIN_USERNAME = "admin"
# Hash the password "admin123" using bcrypt as requested
# Generated with: bcrypt.hashpw(b"admin123", bcrypt.gensalt())
ADMIN_PASSWORD_HASH = b'$2b$12$eX.w.F1.s.i.e.r.s.i.e.u.r.s.i.e.u.r.s.i.e.u.r.s.i.e' # Placeholder, will generate real one in startup if needed or just use a known hash.
# Let's generate a real hash on startup for "admin123" to ensure it works correctly with the installed bcrypt version
ADMIN_PASSWORD_RAW = "admin123"

def check_auth(username, password):
    if username != ADMIN_USERNAME:
        return False
    # In a real app, fetch hash from DB. Here we hash the hardcoded raw password to compare or compare against a stored hash.
    # To strictly follow "Use bcrypt directly", we will verify against a hash.
    # For simplicity in this script, I'll generate the hash once at module level (conceptually) 
    # but practically I'll just hash the input and compare to the known valid logic.
    # Actually, let's just do the standard verify.
    # We will generate the target hash when the app starts if we want, or just hash the input and compare to a variable.
    # But standard practice is checkpw(candidate, hash).
    # So let's store a hash.
    return bcrypt.checkpw(password.encode('utf-8'), VALID_HASH)

# Generate valid hash on startup
VALID_HASH = bcrypt.hashpw(ADMIN_PASSWORD_RAW.encode('utf-8'), bcrypt.gensalt())

# --- Routes ---

@app.route('/')
def home():
    polls = Poll.query.order_by(Poll.created_at.desc()).all()
    return render_template('index.html', polls=polls)

@app.route('/vote/<int:poll_id>', methods=['GET', 'POST'])
def vote(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    
    # Check for cookie
    cookie_name = f'voted_{poll_id}'
    has_voted = request.cookies.get(cookie_name)
    
    if request.method == 'POST':
        if has_voted:
            flash('You have already voted in this poll!', 'error')
            return redirect(url_for('results', poll_id=poll_id))
            
        option_id = request.form.get('option')
        if not option_id:
            flash('Please select an option!', 'error')
            return redirect(url_for('vote', poll_id=poll_id))
        
        option = Option.query.get(option_id)
        if option and option.poll_id == poll.id:
            option.votes += 1
            db.session.commit()
            
            resp = make_response(redirect(url_for('results', poll_id=poll_id)))
            resp.set_cookie(cookie_name, 'true', max_age=60*60*24*365) # 1 year
            return resp
            
    return render_template('vote.html', poll=poll, has_voted=has_voted)

@app.route('/results/<int:poll_id>')
def results(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    total = poll.total_votes()
    return render_template('results.html', poll=poll, total=total)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if check_auth(username, password):
            session['admin'] = True
            return redirect(url_for('create_poll'))
        else:
            flash('Invalid credentials', 'error')
            
    return render_template('login.html')

@app.route('/create', methods=['GET', 'POST'])
def create_poll():
    if not session.get('admin'):
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        question = request.form.get('question')
        options_raw = request.form.getlist('options')
        options = [o.strip() for o in options_raw if o.strip()]
        
        if not question or len(options) < 2:
            flash('Poll must have a question and at least 2 options.', 'error')
        else:
            new_poll = Poll(question=question)
            db.session.add(new_poll)
            db.session.commit()
            
            for opt_text in options:
                new_option = Option(poll_id=new_poll.id, text=opt_text)
                db.session.add(new_option)
            db.session.commit()
            
            flash('Poll created successfully!', 'success')
            return redirect(url_for('home'))
            
    return render_template('create.html')

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

# --- Seeding ---
def seed_database():
    if Poll.query.first() is None:
        print("Seeding database...")
        polls_data = [
            {
                "question": "What is your favorite programming language?",
                "options": ["Python", "JavaScript", "Rust", "Go"],
                "votes": [10, 8, 5, 3]
            },
            {
                "question": "Best time to code?",
                "options": ["Early Morning", "Late Night", "Afternoon"],
                "votes": [4, 15, 2]
            },
            {
                "question": "Tabs or Spaces?",
                "options": ["Tabs", "Spaces", "Mixed (Chaos)"],
                "votes": [12, 20, 1]
            }
        ]
        
        for p_data in polls_data:
            poll = Poll(question=p_data["question"])
            db.session.add(poll)
            db.session.commit()
            
            for i, opt_text in enumerate(p_data["options"]):
                votes = p_data["votes"][i] if i < len(p_data["votes"]) else 0
                option = Option(poll_id=poll.id, text=opt_text, votes=votes)
                db.session.add(option)
            db.session.commit()
        print("Database seeded.")

# --- Main ---
if __name__ == "__main__":
    with app.app_context():
        # Ensure data dir exists
        if not os.path.exists('./data'):
            os.makedirs('./data')
        db.create_all()
        seed_database()
        
    app.run(host="0.0.0.0", port=8000)
