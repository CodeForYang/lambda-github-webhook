.PHONY: test local deploy clean

install:
	python3 -m venv venv
	source ./venv/bin/activate
	pip install -r requirements.txt

test:
	pytest tests/ -v

local:
	sls invoke local -f api -p events/event.json
deploy:
	sls deploy

clean:
	rm -rf .aws-sam/