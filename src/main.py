import json
import logging
import multiprocessing
import sys
from datetime import datetime
from time import sleep

import google.auth
from google.cloud import secretmanager, storage
from pymongo import MongoClient


def get_date_name():
    return datetime.utcnow().isoformat().replace(".", "_")


class CursorMongo(multiprocessing.Process):
    def __init__(
        self, db_url, environment, bucket_storage: storage.Bucket, collection_name: str
    ):
        super().__init__()
        self.db_url = db_url
        self.environment = environment
        self.bucket = bucket_storage
        self.collection_name = collection_name

    def run(self, *args, **kwargs):
        db = MongoClient(self.db_url)[f"ce-db-{self.environment}"]
        cursor = db[self.collection_name].watch(full_document="updateLookup")
        while True:
            data = next(cursor)
            document = data.get("fullDocument")
            if document:
                _id = str(document["_id"])
                data_name = (
                    f"mongoDB/{self.collection_name}/{_id}/{get_date_name()}.json"
                )
                logging.info(data_name)
                self.bucket.blob(data_name).upload_from_string(
                    json.dumps(document, default=str)
                )


class ConnectionValidator:
    def __init__(self, db_url, environment):
        self.db_url = db_url
        self.environment = environment

    def run(self):
        client = MongoClient(self.db_url)
        client.server_info()
        logging.debug("MongoDB Connection in OK")
        client.close()
        sleep(5)


def get_sercret(secret_name="MONGODB_CHANGE_STREAM", is_json=True):
    _, project_id = google.auth.default()
    client = secretmanager.SecretManagerServiceClient()
    logging.info(f"Acessando secret {secret_name}")
    secret_path = client.secret_path(project_id, secret_name)
    secret_latest_version = client.access_secret_version(
        request=secretmanager.AccessSecretVersionRequest(
            {"name": f"{secret_path}/versions/latest"}
        ),
        timeout=5,
    )
    secret_data = secret_latest_version.payload.data.decode("utf-8")
    if is_json:
        return json.loads(secret_data)
    return secret_data


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    logging.info("Inicializando Serviço Mongo Change Stream")
    env = get_sercret()
    MONGODB_URL = get_sercret(secret_name="MONGODB_READ_ONLY", is_json=False)
    BUCKET_NAME = env["BUCKET"]
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    collections_to_stream = env["COLLECTIONS"]

    streams = [
        CursorMongo(MONGODB_URL, env["ENV"], bucket, collection_name)
        for collection_name in collections_to_stream
    ]

    [s.start() for s in streams]

    connection_validator = ConnectionValidator(MONGODB_URL, env["ENV"])
    while True:
        try:
            connection_validator.run()
        except Exception:
            logging.exception("MongoDB is Down! Exiting...")
            [s.terminate() for s in streams]
            sys.exit(1)
