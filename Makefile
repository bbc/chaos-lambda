.PHONY: all test clean zip

all: zip

test:
	PYTHONPATH=src/ python3 -m unittest discover -v test/

clean:
	rm -f chaos-lambda.zip

zip: chaos-lambda.zip

chaos-lambda.zip: src/chaos.py
	zip -j $@ $^
