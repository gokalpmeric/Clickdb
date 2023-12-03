from datetime import datetime

from kubernetes import client, config
import os
import logging

from kubernetes.client import ApiException

from utils import generate_password
from utils.database import collection

logger = logging.getLogger(__name__)

def create_mongodb_deployment(db_name, username, email):
    namespace = os.getenv('K8S_NAMESPACE', 'default')
    password = generate_password()  # Generate a random password

    config.load_kube_config()

    container = client.V1Container(
        name=db_name,
        image="mongo:latest",
        env=[
            client.V1EnvVar(name="MONGO_INITDB_ROOT_USERNAME", value=username),
            client.V1EnvVar(name="MONGO_INITDB_ROOT_PASSWORD", value=password)
        ]
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": db_name}),
        spec=client.V1PodSpec(containers=[container])
    )

    selector = client.V1LabelSelector(match_labels={"app": db_name})
    spec = client.V1DeploymentSpec(replicas=1, selector=selector, template=template)
    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=db_name),
        spec=spec
    )

    apps_v1_api = client.AppsV1Api()
    try:
        apps_v1_api.create_namespaced_deployment(namespace=namespace, body=deployment)
        # Update MongoDB document
        collection.update_one(
            {"db_name": db_name},
            {"$set": {
                "username": username,
                "email": email,
                "status": "created",
                "timestamp": datetime.now(),
                "deleted": False
            }},
            upsert=True
        )
        logger.info(f"MongoDB instance '{db_name}' created by {email}")
        return True, db_name, username, password  # Return the necessary info
    except ApiException as e:
        logger.error(f"Failed to create MongoDB instance '{db_name}': {e}")
        return False, None, None, None