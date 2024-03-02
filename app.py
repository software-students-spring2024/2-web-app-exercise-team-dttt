from flask import Flask, render_template, request, redirect, url_for, session
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from bson.objectid import ObjectId
from os import getenv
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = getenv('FLASK_APP_SECRET_KEY')
bcrypt = Bcrypt(app)

client = MongoClient(getenv('MONGODB_URI'))
db = client['login']
users_collection = db['users']
budget_collection = db['budget']

def validate_user_session():
    if 'userId' in session:
        user_id = session['userId']
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user is None:
            session.clear()
            return False
    else:
        return False
    return True

@app.route('/')
def index():
    if not validate_user_session():
        return redirect(url_for('login'))
    
    user = users_collection.find_one({'_id': ObjectId(session['userId'])})
    user_budget = budget_collection.find({'userId': ObjectId(session['userId'])})
    total_expenses = sum(item['amount'] for item in user_budget)
    total_budget = user.get('total_budget', 0)
    total_income = user.get('total_income', 0)
    remaining_budget = total_budget + total_income - total_expenses
    return render_template('dashboard.html', budget=list(user_budget), total_budget=total_budget, total_income=total_income, remaining_budget=remaining_budget)



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        session.clear()  
    elif request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = users_collection.find_one({'username': username})

        if user and bcrypt.check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['userId'] = str(user['_id'])
            return redirect(url_for('index'))
        else:
            return 'Login Failed'
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    existing_user = users_collection.find_one({'username': username})
    if existing_user is None:
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = users_collection.insert_one({
            'username': username, 
            'password': hashed_password,
            'total_budget': 0,  
            'total_income': 0   
        })
        session['username'] = username
        session['userId'] = str(user.inserted_id)
        return redirect(url_for('index'))
    return 'User already exists'

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('userId', None)
    return redirect(url_for('index'))

@app.route('/add', methods=['GET', 'POST'])
def add_budget():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        budget_entry = {
            'userId': ObjectId(session['userId']),
            'category': request.form.get('category'),
            'amount': float(request.form.get('amount')),
            'description': request.form.get('description'),
            'date': request.form.get('date')
        }
        budget_collection.insert_one(budget_entry)
        return redirect(url_for('index'))
    return render_template('add_budget.html')

@app.route('/edit/<budget_id>', methods=['GET', 'POST'])
def edit_budget(budget_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    budget_entry = budget_collection.find_one({'_id': ObjectId(budget_id), 'userId': ObjectId(session['userId'])})
    if request.method == 'POST':
        updated_entry = {
            '$set': {
                'category': request.form.get('category'),
                'amount': float(request.form.get('amount')),
                'description': request.form.get('description'),
                'date': request.form.get('date')
            }
        }
        budget_collection.update_one({'_id': ObjectId(budget_id)}, updated_entry)
        return redirect(url_for('index'))
    return render_template('edit_budget.html', budget=budget_entry)

@app.route('/delete/<budget_id>', methods=['POST'])
def delete_budget(budget_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    budget_collection.delete_one({'_id': ObjectId(budget_id), 'userId': ObjectId(session['userId'])})
    return redirect(url_for('index'))

@app.route('/search', methods=['GET'])
def search():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    query = request.args.get('query')
    search_results = budget_collection.find({'userId': ObjectId(session['userId']), 'category': query})
    return render_template('dashboard.html', budget=list(search_results))
@app.route('/set_budget', methods=['GET', 'POST'])
def set_budget():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        budget = request.form.get('budget')
        users_collection.update_one({'_id': ObjectId(session['userId'])}, {'$set': {'total_budget': float(budget), 'total_income': 0}})
        return redirect(url_for('index'))
    return render_template('set_budget.html')



@app.route('/add_income', methods=['GET', 'POST'])
def add_income():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        income = request.form.get('income')
        users_collection.update_one({'_id': ObjectId(session['userId'])}, {'$inc': {'total_income': float(income)}})
        return redirect(url_for('index'))
    return render_template('add_income.html')

if __name__ == '__main__':
    app.run(debug=True)
