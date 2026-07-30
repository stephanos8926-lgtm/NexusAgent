from flask import Flask, request, jsonify
import uuid

app = Flask(__name__)

users = {} # In-memory user store

@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    if not data or 'name' not in data or 'email' not in data:
        return jsonify({"error": "Name and email are required"}), 400
    
    user_id = str(uuid.uuid4())
    new_user = {
        "id": user_id,
        "name": data['name'],
        "email": data['email']
    }
    users[user_id] = new_user
    return jsonify(new_user), 201

@app.route('/users', methods=['GET'])
def get_all_users():
    return jsonify(list(users.values())), 200

@app.route('/users/<string:user_id>', methods=['GET'])
def get_user(user_id):
    user = users.get(user_id)
    if user:
        return jsonify(user), 200
    return jsonify({"error": "User not found"}), 404

@app.route('/users/<string:user_id>', methods=['PUT'])
def update_user(user_id):
    user = users.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided for update"}), 400

    user.update(data)
    return jsonify(user), 200

@app.route('/users/<string:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if user_id in users:
        del users[user_id]
        return '', 204
    return jsonify({"error": "User not found"}), 404

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5002)
