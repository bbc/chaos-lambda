SOURCES := $(shell echo src/*.py)
TARGETS := $(patsubst src/%.py,templates/%.json,$(SOURCES))

all: $(TARGETS)

clean:
	rm -f $(TARGETS)

templates/%.json: src/%.py venv
	venv/bin/python $< > $@

venv: requirements.txt
	type virtualenv >/dev/null
	rm -rf $@
	trap "touch -t 200902132331.30 $@" EXIT; virtualenv $@ && venv/bin/pip install -r $<
	touch -r $< $@
