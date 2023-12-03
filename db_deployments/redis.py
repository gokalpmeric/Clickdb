from datetime import datetime

from kubernetes import client, config
import os
import logging

from kubernetes.client import ApiException

from utils.database import collection

logger = logging.getLogger(__name__)
def create_redis_deployment(db_name,email):
    namespace = os.getenv('K8S_NAMESPACE', 'default')
    config.load_kube_config()

    container = client.V1Container(
        name=db_name,
        image="redis:latest",  # Using the latest Redis image
        ports=[client.V1ContainerPort(container_port=6379)]  # Default Redis port
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
        # Update MongoDB document for Redis deployment
        collection.update_one(
            {"db_name": db_name},
            {"$set": {
                "email": email,
                "status": "created",
                "timestamp": datetime.now(),
                "deleted": False
            }},
            upsert=True
        )
        logger.info(f"Redis database '{db_name}' created by {email}")
        return True
    except ApiException as e:
        print(f"Exception when creating Redis deployment: {e}")
        # Handle failed creation
        logger.error(f"Failed to create redis database '{db_name}': {e}")

        return False