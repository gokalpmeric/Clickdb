from datetime import datetime

from kubernetes import client, config
from kubernetes.client import ApiException

from utils.database import collection
from utils.helpers import generate_password
import os
import logging

logger = logging.getLogger(__name__)

def create_postgres_deployment(db_name, username, email):
    namespace = os.getenv('K8S_NAMESPACE', 'default')
    password = generate_password()  # Generate a random password

    config.load_kube_config()

    container = client.V1Container(
        name=db_name,
        image="postgres:latest",
        env=[
            client.V1EnvVar(name="POSTGRES_DB", value=db_name),
            client.V1EnvVar(name="POSTGRES_USER", value=username),
            client.V1EnvVar(name="POSTGRES_PASSWORD", value=password)
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
        logger.info(f"Postgres database '{db_name}' created by {email}")
        return True, db_name, username, password  # Return the necessary info
    except ApiException as e:
        print(f"Exception when creating deployment: {e}")
        # Handle failed creation
        logger.error(f"Failed to create Postgres database '{db_name}': {e}")

        return False, None, None, None

def delete_deployment(db_name):
    namespace = os.getenv('K8S_NAMESPACE', 'default')
    config.load_kube_config()
    apps_v1_api = client.AppsV1Api()
    try:
        # Corrected method call with required arguments
        apps_v1_api.delete_namespaced_deployment(name=db_name, namespace=namespace, body=client.V1DeleteOptions(propagation_policy='Foreground'))
        # Update MongoDB document
        collection.update_one(
            {"db_name": db_name},
            {"$set": {
                "status": "deleted",
                "deleted_at": datetime.now(),
                "deleted": True
            }}
        )
        logger.info(f"Database '{db_name}' deleted")
        return True
    except ApiException as e:
        print(f"Exception when deleting deployment: {e}")
        # Handle failed deletion
        logger.error(f"Failed to delete database '{db_name}': {e}")

        return False