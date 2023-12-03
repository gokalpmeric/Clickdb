from flask import Flask, request, jsonify
from db_deployments import postgres,mongodb,mysql,redis,elasticsearch,kafka
import logging
from dotenv import load_dotenv
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from db_deployments.elasticsearch import create_elasticsearch_deployment
from db_deployments.kafka import create_kafka_deployment, delete_kafka_deployment
from db_deployments.mongodb import create_mongodb_deployment
from db_deployments.mysql import create_mysql_deployment
from db_deployments.postgres import delete_deployment, create_postgres_deployment
from db_deployments.redis import create_redis_deployment
from utils.database import collection
# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

@app.route('/create_database', methods=['POST'])
def create_database():
    data = request.json
    db_name = data.get('database_name')
    username = data.get('username', 'postgres')
    email = data.get('email')

    if not db_name or not email:
        return jsonify({"error": "Database name and email are required"}), 400

    success, db_name, username, password = create_postgres_deployment(db_name, username, email)
    if success:
        return jsonify({"message": "Database created", "db_name": db_name, "username": username, "password": password})
    else:
        return jsonify({"error": "Failed to create database"}), 500

@app.route('/create_redis', methods=['POST'])
def create_redis():
    data = request.json
    db_name = data.get('database_name')
    email = data.get('email')

    if not db_name or not email:
        return jsonify({"error": "Database name and email are required"}), 400

    if create_redis_deployment(db_name, email):
        return jsonify({"message": "Redis creation initiated", "db_name": db_name})
    else:
        return jsonify({"error": "Failed to create Redis instance"}), 500

@app.route('/create_mongodb', methods=['POST'])
def create_mongodb():
    data = request.json
    db_name = data.get('database_name')
    username = data.get('username', 'mongo')  # Default username if not provided
    email = data.get('email')

    if not db_name or not email:
        return jsonify({"error": "Database name and email are required"}), 400

    success, db_name, username, password = create_mongodb_deployment(db_name, username, email)
    if success:
        return jsonify({
            "message": "MongoDB database creation initiated",
            "db_name": db_name,
            "username": username,
            "password": password
        })
    else:
        return jsonify({"error": "Failed to create MongoDB database"}), 500

@app.route('/create_mysql', methods=['POST'])
def create_mysql():
    data = request.json
    db_name = data.get('database_name')
    email = data.get('email')

    if not db_name or not email:
        return jsonify({"error": "Database name and email are required"}), 400

    success, db_name, password = create_mysql_deployment(db_name, email)
    if success:
        return jsonify({
            "message": "MySQL deployment initiated",
            "db_name": db_name,
            "password": password  # Returning the password; ensure this is done securely
        })
    else:
        return jsonify({"error": "Failed to deploy MySQL"}), 500

@app.route('/create_kafka', methods=['POST'])
def create_kafka():
    data = request.json
    db_name = data.get('database_name')
    email = data.get('email')

    if not db_name or not email:
        return jsonify({"error": "Database name and email are required"}), 400

    success, db_name = create_kafka_deployment(db_name, email)
    if success:
        return jsonify({"message": "Kafka deployment initiated", "db_name": db_name})
    else:
        return jsonify({"error": "Failed to deploy Kafka"}), 500

@app.route('/create_elasticsearch', methods=['POST'])
def create_elasticsearch():
    data = request.json
    db_name = data.get('database_name')
    email = data.get('email')

    if not db_name or not email:
        return jsonify({"error": "Database name and email are required"}), 400

    success, db_name = create_elasticsearch_deployment(db_name, email)
    if success:
        return jsonify({"message": "Elasticsearch deployment initiated", "db_name": db_name})
    else:
        return jsonify({"error": "Failed to deploy Elasticsearch"}), 500

@app.route('/delete_database', methods=['POST'])
def delete_database():
    data = request.json
    db_name = data.get('database_name')

    if not db_name:
        return jsonify({"error": "Database name is required"}), 400

    if delete_deployment(db_name):
        return jsonify({"message": "Database deletion initiated", "db_name": db_name})
    else:
        return jsonify({"error": "Failed to delete database"}), 500


@app.route('/delete_redis', methods=['POST'])
def delete_redis():
    data = request.json
    db_name = data.get('database_name')

    if not db_name:
        return jsonify({"error": "Database name is required"}), 400

    if delete_deployment(db_name):
        return jsonify({"message": "Redis deletion initiated", "db_name": db_name})
    else:
        return jsonify({"error": "Failed to delete Redis instance"}), 500
@app.route('/delete_kafka', methods=['POST'])
def delete_kafka():
    data = request.json
    db_name = data.get('database_name')

    if not db_name:
        return jsonify({"error": "Database name is required"}), 400

    if delete_kafka_deployment(db_name):
        return jsonify({"message": "Kafka deletion initiated", "db_name": db_name})
    else:
        return jsonify({"error": "Failed to delete Kafka instance"}), 500

@app.route('/get_deployment_logs', methods=['GET'])
def get_deployment_logs():
    namespace = request.args.get('namespace', 'default')
    deployment_name = request.args.get('deployment_name')

    if not deployment_name:
        return jsonify({"error": "Deployment name is required"}), 400

    try:
        core_v1_api = client.CoreV1Api()
        pods = core_v1_api.list_namespaced_pod(namespace, label_selector=f"app={deployment_name}")

        logs = {}
        for pod in pods.items:
            pod_name = pod.metadata.name
            pod_logs = core_v1_api.read_namespaced_pod_log(name=pod_name, namespace=namespace)
            logs[pod_name] = pod_logs

        return jsonify({"logs": logs})
    except ApiException as e:
        print(f"Exception when fetching deployment logs: {e}")
        return jsonify({"error": "Failed to fetch deployment logs"}), 500


@app.route('/list_databases', methods=['GET'])
def list_databases():
    user_email = request.args.get('email')
    if not user_email:
        return jsonify({"error": "Email is required"}), 400

    query = {"email": user_email, "deleted": False}
    active_databases = collection.find(query, {"_id": 0, "db_name": 1, "timestamp": 1})

    return jsonify(list(active_databases))

@app.route('/list_kafka', methods=['GET'])
def list_kafka():
    user_email = request.args.get('email')
    if not user_email:
        return jsonify({"error": "Email is required"}), 400

    query = {"email": user_email, "deleted": False, "type": "kafka"}
    kafka_instances = collection.find(query, {"_id": 0, "db_name": 1, "timestamp": 1})

    return jsonify(list(kafka_instances))


if __name__ == '__main__':
    app.run(debug=True)
