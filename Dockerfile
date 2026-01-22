# syntax=docker/dockerfile:1

FROM python:3.14-slim

ARG PIP_DISABLE_PIP_VERSION_CHECK=1
ARG PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY . .

RUN groupadd -r amouser && useradd -r -g amouser amouser

RUN chown -R amouser:amouser /app

USER amouser

CMD [ "python3", "main.py"]
