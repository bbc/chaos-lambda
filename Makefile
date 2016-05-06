.PHONY: all test clean zip

all: test zip

venv: test-requirements.txt
	type pip virtualenv >/dev/null
	test -d venv || virtualenv --no-site-packages venv
	trap 'touch -d @1234567890 venv' EXIT; venv/bin/pip install -r test-requirements.txt
	touch -r test-requirements.txt venv

test: venv
	venv/bin/nosetests -v

clean:
	rm -f chaos-lambda.zip
	rm -rf venv

zip: chaos-lambda.zip

chaos-lambda.zip: src/chaos.py
	zip -j $@ $^
