.PHONY: all test clean zip

all: zip

venv: test-requirements.txt
	type virtualenv >/dev/null
	(virtualenv $@ && $@/bin/pip install -r $<) || rm -rf $@

test: venv
	venv/bin/nosetests -v

clean:
	rm -f chaos-lambda.zip
	rm -rf venv

zip: chaos-lambda.zip

chaos-lambda.zip: src/chaos.py
	zip -j $@ $^
