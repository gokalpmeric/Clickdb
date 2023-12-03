from datetime import datetime

from kubernetes import client, config
import os
import logging

from kubernetes.client import ApiException

from utils.database import collection

logger = logging.getLogger(__name__)
def create_kafka_deployment(db_name, email):
    namespace = os.getenv('K8S_NAMESPACE', 'default')
    config.load_kube_config()

    # Zookeeper Deployment
    zookeeper_container = client.V1Container(
        name=f"{db_name}-zookeeper",
        image="bitnami/zookeeper:latest",
        env=[
            client.V1EnvVar(name="ALLOW_ANONYMOUS_LOGIN", value="yes"),
        ]
    )
    zookeeper_template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": f"{db_name}-zookeeper"}),
        spec=client.V1PodSpec(containers=[zookeeper_container])
    )
    zookeeper_selector = client.V1LabelSelector(match_labels={"app": f"{db_name}-zookeeper"})
    zookeeper_spec = client.V1DeploymentSpec(replicas=1, selector=zookeeper_selector, template=zookeeper_template)
    zookeeper_deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=f"{db_name}-zookeeper"),
        spec=zookeeper_spec
    )

    # Kafka Deployment
    kafka_container = client.V1Container(
        name=db_name,
        image="bitnami/kafka:latest",
        env=[
            client.V1EnvVar(name="KAFKA_CFG_ZOOKEEPER_CONNECT", value=f"{db_name}-zookeeper:2181"),
            client.V1EnvVar(name="ALLOW_PLAINTEXT_LISTENER", value="yes"),
        ]
    )
    kafka_template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": db_name}),
        spec=client.V1PodSpec(containers=[kafka_container])
    )
    kafka_selector = client.V1LabelSelector(match_labels={"app": db_name})
    kafka_spec = client.V1DeploymentSpec(replicas=1, selector=kafka_selector, template=kafka_template)
    kafka_deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=db_name),
        spec=kafka_spec
    )

    apps_v1_api = client.AppsV1Api()
    core_v1_api = client.CoreV1Api()

    try:
        # Deploy Zookeeper Deployment
        apps_v1_api.create_namespaced_deployment(namespace=namespace, body=zookeeper_deployment)

        # Deploy Kafka Deployment
        apps_v1_api.create_namespaced_deployment(namespace=namespace, body=kafka_deployment)

        # Zookeeper Service
        zookeeper_service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=f"{db_name}-zookeeper"),
            spec=client.V1ServiceSpec(
                selector={"app": f"{db_name}-zookeeper"},
                ports=[client.V1ServicePort(port=2181, target_port=2181)]
            )
        )
        # Deploy Zookeeper Service
        core_v1_api.create_namespaced_service(namespace=namespace, body=zookeeper_service)

        # Kafka Service
        kafka_service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=db_name),
            spec=client.V1ServiceSpec(
                selector={"app": db_name},
                ports=[client.V1ServicePort(port=9092, target_port=9092)]
            )
        )
        # Deploy Kafka Service
        core_v1_api.create_namespaced_service(namespace=namespace, body=kafka_service)
        collection.insert_one({
            "db_name": db_name,
            "email": email,
            "type": "kafka",  # Specify the type as Kafka
            "status": "created",
            "timestamp": datetime.now(),
            "deleted": False
        })
        logger.info(f"Kafka instance '{db_name}' with Zookeeper created by {email}")
        return True, db_name
    except ApiException as e:
        logger.error(f"Failed to create Kafka instance '{db_name}' with Zookeeper: {e}")
        return False, None

def delete_kafka_deployment(db_name):
    namespace = os.getenv('K8S_NAMESPACE', 'default')
    config.load_kube_config()

    apps_v1_api = client.AppsV1Api()
    core_v1_api = client.CoreV1Api()

    try:
        # Delete Kafka Deployment
        apps_v1_api.delete_namespaced_deployment(name=db_name, namespace=namespace)

        # Delete Zookeeper Deployment
        apps_v1_api.delete_namespaced_deployment(name=f"{db_name}-zookeeper", namespace=namespace)

        # Delete Kafka Service
        core_v1_api.delete_namespaced_service(name=db_name, namespace=namespace)

        # Delete Zookeeper Service
        core_v1_api.delete_namespaced_service(name=f"{db_name}-zookeeper", namespace=namespace)

        # Update MongoDB document to mark as deleted
        collection.update_one(
            {"db_name": db_name, "type": "kafka"},
            {"$set": {"deleted": True, "deleted_at": datetime.now()}}
        )
        collection.update_one(
            {"db_name": db_name, "type": "kafka"},
            {"$set": {"deleted": True, "deleted_at": datetime.now()}}
        )

        logger.info(f"Kafka instance '{db_name}' deleted")
        return True
    except ApiException as e:
        logger.error(f"Failed to delete Kafka instance '{db_name}': {e}")
        return False