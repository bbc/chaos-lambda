.PHONY: all test clean zip

all: zip

venv: test-requirements.txt
	type virtualenv >/dev/null
	rm -rf $@
	trap "touch -t 200902132331.30 $@" EXIT; virtualenv $@ && $@/bin/pip install -r $<
	touch -r $< $@

test: venv
	venv/bin/nosetests -v

clean:
	rm -f chaos-lambda.zip
	rm -rf venv

zip: chaos-lambda.zip

chaos-lambda.zip: src/chaos.py
	zip -j $@ $^
