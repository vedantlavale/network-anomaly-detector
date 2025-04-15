from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os

# User model
class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

    @classmethod
    def get(cls, user_id):
        users = load_users()
        if user_id in users:
            user_data = users[user_id]
            return cls(user_id, user_data['username'], user_data['password_hash'])
        return None

def load_users():
    users_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/users.json')
    if not os.path.exists(users_path):
        return {}
    with open(users_path, 'r') as f:
        return json.load(f)

def init_login_manager(app):
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.get(user_id)