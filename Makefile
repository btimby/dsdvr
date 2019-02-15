DOCKER=docker
TAG=btimby/dsdvr
DSDVR=$(find dsdvr -type f -name '*.py')

.PHONY: all clean container run

all: run

dist/dsdvr-0.1.tar.gz: ${DSDVR}
	python3 setup.py sdist

container: dist/dsdvr-0.1.tar.gz
	${DOCKER} build -t ${TAG}:latest .

migrations:
	${MAKE} -C backend $@

migrate:
	${MAKE} -C backend $@

run:
	docker run

clean:
	rm -rf build dist *.egg-info
