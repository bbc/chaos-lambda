.PHONY: all test clean zip

all: test zip

venv: test-requirements.txt
	type virtualenv >/dev/null
	if [ -d venv ]; then rm -rf venv; fi
	trap "touch -t 200902132331.30 venv" EXIT; virtualenv venv && venv/bin/pip install -r test-requirements.txt
	touch -r test-requirements.txt venv

test: venv
	venv/bin/nosetests -v

clean:
	rm -f chaos-lambda.zip
	rm -rf venv

zip: chaos-lambda.zip

chaos-lambda.zip: src/chaos.py
	zip -j $@ $^
