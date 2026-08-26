.PHONY: test demo receipt sweep

test:
	python3 -m unittest discover -s tests -v

demo:
	python3 -m gate incomplete-laws
	python3 -m gate declared-laws

receipt:
	python3 -m gate $(EXAMPLE) --json

sweep:
	python3 tools/sweep.py --history

calibrate:
	python3 tools/calibrate.py $(RUNS)

explain:
	python3 -m explainer $(EXAMPLE)

attacks:
	python3 -m attacks

sabotage:
	python3 -m attacks --sabotage

results:
	python3 -m attacks --write

ui:
	python3 -m web --port $(or $(PORT),7690)

record:
	python3 tools/record.py

sync:
	python3 tools/sync_readme.py

readback:
	python3 tools/readback.py --base-url $(BASE_URL) --runs $(or $(RUNS),10)
