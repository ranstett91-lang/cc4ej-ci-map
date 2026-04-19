# cc4ej-ci-map — ingest pipeline driver
#
# Everything that touches the network, the hash lock, or the rebuild goes
# through these targets so CI and a human rebuilding from a clean clone take
# the same path. See docs/INGEST_ARCHITECTURE.md for the full design.

PY      ?= python3
SOURCE  ?= ejscreen
VINTAGES ?=

.PHONY: help deps fetch verify rebuild history clean-raw

help:
	@echo "Targets:"
	@echo "  deps                 install ingest python deps"
	@echo "  fetch SOURCE=<id>    fetch + lock every configured vintage of SOURCE"
	@echo "                       override with VINTAGES='2023 2024' to narrow"
	@echo "  verify               hash-check every locked file against disk (CI runs this)"
	@echo "  history              rebuild de_blockgroups_history.json from locked snapshots"
	@echo "  rebuild              fetch ejscreen + verify + history (end-to-end from clean)"
	@echo "  clean-raw            delete data_raw/ (hashes in lock stay; next fetch re-downloads)"

deps:
	$(PY) -m pip install -r ingest/requirements.txt

fetch:
	@if [ -z "$(VINTAGES)" ]; then \
	  $(PY) -m ingest.snapshots --source $(SOURCE); \
	else \
	  $(PY) -m ingest.snapshots --source $(SOURCE) --vintages $$(echo $(VINTAGES) | tr ' ' ','); \
	fi

verify:
	$(PY) -m ingest.verify

history:
	$(PY) scripts/fetch_ejscreen_history.py

rebuild: fetch verify history

clean-raw:
	rm -rf data_raw
