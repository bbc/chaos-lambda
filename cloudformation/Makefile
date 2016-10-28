SOURCES := $(shell echo src/*.py)
TARGETS := $(patsubst src/%.py,templates/%.json,$(SOURCES)) templates/lambda_standalone.json

CHAOS_PY := ../src/chaos.py

all: $(TARGETS)

clean:
	rm -f $(TARGETS)

templates/lambda_standalone.json: src/lambda.py $(CHAOS_PY) venv
	venv/bin/python $< $(CHAOS_PY) > $@

templates/%.json: src/%.py venv
	venv/bin/python $< > $@

venv: requirements.txt
	type virtualenv >/dev/null
	rm -rf $@
	trap "touch -t 200902132331.30 $@" EXIT; virtualenv $@ && venv/bin/pip install -r $<
	touch -r $< $@
