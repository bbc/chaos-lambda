SOURCES := $(shell echo src/*.py)
TARGETS := $(patsubst src/%.py,templates/%.json,$(SOURCES))

all: $(TARGETS)

clean:
	rm -f $(TARGETS)

templates/%.json: src/%.py
	python $< > $@
