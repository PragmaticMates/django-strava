.PHONY: clean build upload upload-test

clean:
	rm -rf dist/ build/ *.egg-info

build: clean
	python -m build

upload: build
	twine upload dist/*

upload-test: build
	twine upload --repository testpypi dist/*
