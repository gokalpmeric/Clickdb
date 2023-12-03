from datetime import datetime

from kubernetes import client, config
import os
import logging

from kubernetes.client import ApiException

from utils import generate_password
from utils.database import collection

logger = logging.getLogger(__name__)

def create_mysql_deployment(db_name, email):
    namespace = os.getenv('K8S_NAMESPACE', 'default')
    password = generate_password()  # Generate a random password for MySQL
    config.load_kube_config()

    # MySQL Deployment
    mysql_container = client.V1Container(
        name=db_name,
        image="mysql:8.0",
        env=[
            client.V1EnvVar(name="MYSQL_ROOT_PASSWORD", value=password),
            # Optional: Set this if you want to use the legacy authentication method
            # client.V1EnvVar(name="MYSQL_USER", value="user"),
            # client.V1EnvVar(name="MYSQL_PASSWORD", value="userpassword"),
            # client.V1EnvVar(name="MYSQL_DATABASE", value="mydatabase"),
        ]
    )

    mysql_template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": db_name}),
        spec=client.V1PodSpec(containers=[mysql_container])
    )

    mysql_selector = client.V1LabelSelector(match_labels={"app": db_name})
    mysql_spec = client.V1DeploymentSpec(replicas=1, selector=mysql_selector, template=mysql_template)
    mysql_deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=db_name),
        spec=mysql_spec
    )

    apps_v1_api = client.AppsV1Api()
    core_v1_api = client.CoreV1Api()

    try:
        # Deploy MySQL Deployment
        apps_v1_api.create_namespaced_deployment(namespace=namespace, body=mysql_deployment)

        # MySQL Service
        mysql_service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=db_name),
            spec=client.V1ServiceSpec(
                selector={"app": db_name},
                ports=[client.V1ServicePort(port=3306, target_port=3306)]
            )
        )
        # Deploy MySQL Service
        core_v1_api.create_namespaced_service(namespace=namespace, body=mysql_service)

        # Insert a document into MongoDB for MySQL deployment
        collection.insert_one({
            "db_name": db_name,
            "email": email,
            "type": "mysql",
            "status": "created",
            "timestamp": datetime.now(),
            "deleted": False,
            "password": password  # Store the generated password
        })

        logger.info(f"MySQL instance '{db_name}' created by {email}")
        return True, db_name, password
    except ApiException as e:
        logger.error(f"Failed to create MySQL instance '{db_name}': {e}")
        return False, None, None