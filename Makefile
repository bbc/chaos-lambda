.PHONY: test clean zip

all: test zip

test:
	nosetests -v

clean:
	rm -f lambda-monkey.zip

zip: lambda-monkey.zip

lambda-monkey.zip: src/lmonkey.py
	zip -j $@ src/lmonkey.py
