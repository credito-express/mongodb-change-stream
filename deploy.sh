#!/bin/bash

gcloud auth print-access-token  | docker login -u oauth2accesstoken --password-stdin https://us-central1-docker.pkg.dev
docker build -t mongo-change-stream .
docker tag mongo-change-stream us-central1-docker.pkg.dev/creditoexpress-dev/mongo-change-stream/mongo-change-stream
docker push us-central1-docker.pkg.dev/creditoexpress-dev/mongo-change-stream/mongo-change-stream
