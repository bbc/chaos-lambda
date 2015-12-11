.PHONY: all test clean zip

all: test zip

test:
	nosetests -v

clean:
	rm -f chaos-lambda.zip

zip: chaos-lambda.zip

chaos-lambda.zip: src/chaos.py
	zip -j $@ $^
