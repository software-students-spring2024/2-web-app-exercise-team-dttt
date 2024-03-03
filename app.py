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
income_collection = db['income']
spending_collection = db['spending']

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
    
    user_id = ObjectId(session['userId'])
    user = users_collection.find_one({'_id': user_id})
    user_budget = budget_collection.find({'userId': user_id})
    spending_entries = spending_collection.find({'userId': user_id})
    income_entries = income_collection.find({'userId': user_id})
    total_spending = sum(item['amount'] for item in spending_entries)
    total_budget = user.get('total_budget', 0)
    total_income = sum(item['amount'] for item in income_entries)
    remaining_budget = total_budget + total_income - total_spending
    return render_template('dashboard.html', search_results=list(spending_entries), budget=list(user_budget), total_spending=total_spending,total_budget=total_budget, total_income=total_income, remaining_budget=remaining_budget)



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
            'total_income': 0,
            'total_spending': 0   
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

@app.route('/view_spending')
def view_spending():
    spendings = spending_collection.find({'userId': ObjectId(session['userId'])})
    return render_template('view_spending.html', spendings=spendings)

@app.route('/view_income')
def view_income():
    incomes = income_collection.find({'userId': ObjectId(session['userId'])})
    return render_template('view_income.html', incomes=incomes)

@app.route('/add_income', methods=['GET', 'POST'])
def add_income():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        income_source = request.form.get('source')
        income_amount = request.form.get('income')
        income_date = request.form.get('income_date')
        income_entry = {
            'source': income_source,
            'userId': ObjectId(session['userId']),
            'amount': float(income_amount),
            'date': income_date
        }
        income_collection.insert_one(income_entry)
        users_collection.update_one(
            {'_id': ObjectId(session['userId'])}, 
            {'$inc': {'total_income': float(income_amount)}}
        )
        return redirect(url_for('view_income'))
    return render_template('add_income.html')

@app.route('/add_spending', methods=['GET', 'POST'])
def add_spending():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        spending_entry = {
            'userId': ObjectId(session['userId']),
            'category': request.form.get('category'),
            'amount': float(request.form.get('amount')),
            'description': request.form.get('description'),
            'date': request.form.get('date')
        }
        spending_collection.insert_one(spending_entry)
        users_collection.update_one(
            {'_id': ObjectId(session['userId'])}, 
            {'$inc': {'total_spending': amount}}
        )
        return redirect(url_for('view_spending'))
    return render_template('add_spending.html')

@app.route('/edit_income/<income_id>', methods=['GET', 'POST'])
def edit_income(income_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    income_entry = income_collection.find_one({'_id': ObjectId(income_id), 'userId': ObjectId(session['userId'])})
    if request.method == 'POST':
        updated_entry = {
            '$set': {
                'source': request.form.get('source'),
                'amount': float(request.form.get('amount')),
                'description': request.form.get('description'),
                'date': request.form.get('date')
            }
        }
        income_collection.update_one({'_id': ObjectId(income_id)}, updated_entry)
        return redirect(url_for('view_income'))
    return render_template('edit_income.html', income=income_entry)

@app.route('/edit_spending/<spending_id>', methods=['GET', 'POST'])
def edit_spending(spending_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    spending_entry = spending_collection.find_one({'_id': ObjectId(spending_id), 'userId': ObjectId(session['userId'])})
    if request.method == 'POST':
        updated_entry = {
            '$set': {
                'category': request.form.get('category'),
                'amount': float(request.form.get('amount')),
                'description': request.form.get('description'),
                'date': request.form.get('date')
            }
        }
        spending_collection.update_one({'_id': ObjectId(spending_id)}, updated_entry)
        return redirect(url_for('view_spending'))
    
    return render_template('edit_spending.html', spending=spending_entry)

@app.route('/delete_income/<income_id>', methods=['POST'])
def delete_income(income_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    income_collection.delete_one({'_id': ObjectId(income_id), 'userId': ObjectId(session['userId'])})
    return redirect(url_for('view_income'))

@app.route('/delete_spending/<spending_id>', methods=['POST'])
def delete_spending(spending_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    spending_collection.delete_one({'_id': ObjectId(spending_id), 'userId': ObjectId(session['userId'])})
    return redirect(url_for('view_spending'))


@app.route('/search_spending', methods=['GET'])
def search_spending():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = ObjectId(session['userId'])
    query = request.args.get('query')
    
    search_results = spending_collection.find({'userId': user_id, 'category': {'$regex': query, '$options': 'i'}})
    search_results = list(search_results)      

    return render_template('view_spending.html', spendings=search_results)

@app.route('/search_income', methods=['GET'])
def search_income():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = ObjectId(session['userId'])
    query = request.args.get('query')
    
    search_results = income_collection.find({'userId': user_id, 'source': {'$regex': query, '$options': 'i'}})
    search_results = list(search_results)  
    return render_template('view_income.html', incomes=search_results)



@app.route('/set_budget', methods=['GET', 'POST'])
def set_budget():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        budget = request.form.get('budget')
        users_collection.update_one(
            {'_id': ObjectId(session['userId'])}, 
            {'$set': {'total_budget': float(budget), 
            'total_income': 0}})
        return redirect(url_for('index'))
    return render_template('set_budget.html')


if __name__ == '__main__':
    app.run(debug=True)
