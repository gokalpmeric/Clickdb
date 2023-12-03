from datetime import datetime

from kubernetes import client, config
import os
import logging

from kubernetes.client import ApiException
from pymongo import MongoClient

from utils.database import collection

logger = logging.getLogger(__name__)
def create_elasticsearch_deployment(db_name, email):
    namespace = os.getenv('K8S_NAMESPACE', 'default')
    config.load_kube_config()

    # Elasticsearch Deployment
    elasticsearch_container = client.V1Container(
        name=db_name,
        image="docker.elastic.co/elasticsearch/elasticsearch:7.10.0",
        env=[
            client.V1EnvVar(name="discovery.type", value="single-node")
        ]
    )

    elasticsearch_template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": db_name}),
        spec=client.V1PodSpec(containers=[elasticsearch_container])
    )

    elasticsearch_selector = client.V1LabelSelector(match_labels={"app": db_name})
    elasticsearch_spec = client.V1DeploymentSpec(replicas=1, selector=elasticsearch_selector, template=elasticsearch_template)
    elasticsearch_deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=db_name),
        spec=elasticsearch_spec
    )

    apps_v1_api = client.AppsV1Api()
    core_v1_api = client.CoreV1Api()

    try:
        # Deploy Elasticsearch Deployment
        apps_v1_api.create_namespaced_deployment(namespace=namespace, body=elasticsearch_deployment)

        # Elasticsearch Service
        elasticsearch_service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=db_name),
            spec=client.V1ServiceSpec(
                selector={"app": db_name},
                ports=[client.V1ServicePort(port=9200, target_port=9200)]
            )
        )
        # Deploy Elasticsearch Service
        core_v1_api.create_namespaced_service(namespace=namespace, body=elasticsearch_service)

        # Insert a document into MongoDB for Elasticsearch deployment
        collection.insert_one({
            "db_name": db_name,
            "email": email,
            "type": "elasticsearch",
            "status": "created",
            "timestamp": datetime.now(),
            "deleted": False
        })

        logger.info(f"Elasticsearch instance '{db_name}' created by {email}")
        return True, db_name
    except ApiException as e:
        logger.error(f"Failed to create Elasticsearch instance '{db_name}': {e}")
        return False, None