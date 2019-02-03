DOCKER=docker
TAG=btimby/dsdvr
DSDVR=$(find dsdvr -type f -name '*.py')

.PHONY: all clean container run

all: run

dist/dsdvr-0.1.tar.gz: ${DSDVR}
	python3 setup.py sdist

container: dist/dsdvr-0.1.tar.gz
	${DOCKER} build -t ${TAG}:latest .

resetmigrations:
	rm -rf dsdvr/api/migrations/0*.py*
	rm -rf dsdvr/db.sqlite3
	$(MAKE) migrations
	$(MAKE) migrate

migrations:
	pipenv run python dsdvr/manage.py makemigrations

migrate:
	pipenv run python dsdvr/manage.py migrate

run:
	pipenv run python dsdvr/manage.py runserver

clean:
	rm -rf build dist *.egg-info
