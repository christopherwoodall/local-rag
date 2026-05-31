#!/usr/bin/make -f
# -*- makefile -*-

SHELL         := /bin/bash
.SHELLFLAGS   := -eu -o pipefail -c
.DEFAULT_GOAL := help
.LOGGING      := 0

.ONESHELL:             ;	# Recipes execute in same shell
.NOTPARALLEL:          ;	# Wait for this target to finish
.SILENT:               ;	# No need for @
.EXPORT_ALL_VARIABLES: ;	# Export variables to child processes.
.DELETE_ON_ERROR:      ;	# Delete target if recipe fails.

# Modify the block character to be `-\t` instead of `\t`
ifeq ($(origin .RECIPEPREFIX), undefined)
	$(error This version of Make does not support .RECIPEPREFIX.)
endif
.RECIPEPREFIX = -


PROJECT_DIR := $(shell git rev-parse --show-toplevel)
SRC_DIR     := $(PROJECT_DIR)/src
BUILD_DIR   := $(PROJECT_DIR)/dist
RUN_DIR     := $(PROJECT_DIR)/runs

default: $(.DEFAULT_GOAL)
all: help

# -----------------------------------------------------------------------------
# Commands
# -----------------------------------------------------------------------------
# Each command should be defined as a separate target with a description.
# Example:
# .PHONY: my-command
# my-command: ## Description of what my-command does
# -	@echo "Running my-command..."

.PHONY: help
help: ## List commands <default>
-	echo -e "USAGE: make \033[36m[COMMAND]\033[0m\n"
-	echo "Available commands:"
-	awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\t\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)


.PHONY: install
install: ## Install all dependencies (incl. dev) via uv
-	uv sync --extra dev


.PHONY: up
up: ## Start docker services (qdrant + mongo)
-	docker compose up -d


.PHONY: down
down: ## Stop and remove docker services (data preserved)
-	docker compose down


.PHONY: logs
logs: ## Tail docker service logs (qdrant + mongo)
-	docker compose logs -f --tail=100


.PHONY: serve
serve: ## Run the RAG API server (uvicorn on :8000)
-	uv run start-rag-server


.PHONY: run
run: ## Start docker services, then run the RAG server
-	docker compose up -d
-	uv run start-rag-server


.PHONY: clean
clean: ## Stop services + remove build/cache artifacts (KEEPS db data)
-	docker compose down
-	rm -rf $(BUILD_DIR) $(SRC_DIR)/*.egg-info $(PROJECT_DIR)/.ruff_cache
-	find $(PROJECT_DIR) -type d -name '__pycache__' -prune -exec rm -rf {} +


.PHONY: build
build: ## Build the application wheel
-	uv pip install --editable .
-	hatch build --clean --target wheel


.PHONY: lint
lint: ## Lint and format the code
-	ruff check $(SRC_DIR) --fix
-	ruff format $(SRC_DIR)


.PHONY: tree
tree: ## Display project structure
-	tree -I 'dist|build|*.egg-info|__pycache__' $(SRC_DIR)


.PHONY: lines
lines: ## Count lines of code
-	find $(SRC_DIR) -name '*.py' -print0 | xargs -0 wc -l
