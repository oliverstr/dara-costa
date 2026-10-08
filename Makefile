# Local build + preview, mirroring .github/workflows/pages.yml.
#   make          build services.json and both language pages
#   make serve    build, then serve public/live at http://localhost:$(PORT)
#   make clean    remove generated files

PORT ?= 8000
OUT := public/live
CSV := $(lastword $(sort $(wildcard $(OUT)/assets/*_items-export_*.csv)))

.PHONY: build services pages serve clean

build: services pages

services:
	@test -n "$(CSV)" || { echo "No SumUp export found in $(OUT)/assets/"; exit 1; }
	python3 .github/scripts/csv_to_json.py "$(CSV)" $(OUT)/assets/services.json

pages:
	python3 .github/scripts/render_i18n.py src/index.template.html i18n $(OUT)

serve: build
	@echo "German:     http://localhost:$(PORT)/"
	@echo "Portuguese: http://localhost:$(PORT)/pt/"
	python3 -m http.server $(PORT) -d $(OUT)

clean:
	rm -rf $(OUT)/index.html $(OUT)/pt $(OUT)/assets/services.json
