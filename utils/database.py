# utils/database.py or db/database.py
from pymongo import MongoClient

mongo_client = MongoClient("mongodb://localhost:27017/")
db = mongo_client["deployment_logs"]
collection = db["postgres_deployments"]
