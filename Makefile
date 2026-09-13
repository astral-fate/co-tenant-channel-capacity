# Covert channels through shared agent infrastructure -- reproduction entry points.
#
# The capacity arm needs no model and no network: `make capacity` reproduces every
# headline number from a clean checkout. The behavioural arm needs provider keys.

.PHONY: help verify capacity joint paper slides real screen test clean

help:
	@echo "verify    - recompute every claim and check the manuscript agrees"
	@echo "capacity  - re-measure the closure ladder (no model, no network)"
	@echo "joint     - re-measure the joint encoder"
	@echo "screen    - rebuild the model screen from run artifacts"
	@echo "paper     - render main.tex from results/ and build the PDF"
	@echo "real      - probe the real substrate (Docker: tiers 1-3)"
	@echo "test      - substrate + analysis pipeline tests"

verify:
	python paper/render.py --list
	python analyze/verify.py

capacity:
	python src/capacity.py

joint:
	python src/joint.py

screen:
	python analyze/model_screen.py

paper:
	python paper/render.py
	cd paper && bash build.sh

slides:
	@echo "slides.html is static -- open it, or print to PDF (A4 landscape)"

real:
	docker compose -f real/docker-compose.yml run --rm --build probe
	docker compose -f real/docker-compose.yml run --rm probe-store

test:
	python src/test_substrate.py
	python analyze/test_pipeline.py

clean:
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	rm -f paper/main.aux paper/main.log paper/main.out paper/main.bbl paper/main.blg
