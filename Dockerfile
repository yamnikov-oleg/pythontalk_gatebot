FROM python:3.7-alpine

RUN apk --no-cache add build-base libffi-dev postgresql-dev

RUN mkdir /app
WORKDIR /app

ADD requirements.txt .
RUN pip install -r requirements.txt

ADD . /app

CMD [ "python", "./run.py" ]
