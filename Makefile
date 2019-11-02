.PHONY: default push test check unit functional lint types imports fiximports readme coverage branch popclean

# This is the first thing in the makefile so it is the default when just "make" is run
# and something else doesn't get run by accident.
default:
	@echo "Heroic doesn't get that affected by Barbs. Bogles though. Kills their creature, kills their face."

# Push your commits (safely) to the remote branch.
push:
	@git pull origin master && make test && git push --set-upstream origin `git rev-parse --abbrev-ref HEAD`

# Run all unit and syntax tests.
test: check unit

# Run all typechecking and linting.
check: lint jslint types imports

# Create a pull request, requies 'hub' from github.
pr:
	hub pull-request

# Run all tests, push and create pull request.
release: push pr

buildjs:
	webpack --config=decksite/webpack.config.js

# Run unit tests.
TEST=.
unit:
	@echo
	@echo "******************************** Unit Tests ***********************************"
	@echo
	@find . -name "*$(TEST)*" | grep _test.py$$ | xargs python3 dev.py tests -x -m "not functional and not perf"
	@echo

# Run functional tests.
functional:
	@echo
	@echo "******************************** Functional Tests ******************************"
	@echo
	@find . -name "*$(TEST)*" | grep _test.py$$ | xargs python3 dev.py tests -x -m "functional"
	@echo

# Run perf tests.
perf:
	@echo
	@echo "******************************** Performance Tests *****************************"
	@echo
	@find . -name "*$(TEST)*" | grep _test.py$$ | xargs python3 dev.py tests -x -m "perf"
	@echo

# Run lint on all python files.
lint:
	@echo
	@echo "******************************** Lint *****************************************"
	@echo
	@python3 dev.py pylint
	@echo

jslint:
	@echo
	@echo "******************************** JS Lint **************************************"
	@echo
	@! git ls-files | grep "\.js$$" | xargs js-beautify | grep -v unchanged
	@echo

types:
	@echo
	@echo "******************************** Typechecking *********************************"
	@python3 dev.py types
	@echo

imports:
	@echo
	@echo "******************************** Import Ordering ******************************"
	@echo
	@python3 dev.py imports
	@echo

fiximports:
	@echo
	@echo "******************************** Import Ordering ******************************"
	@echo
	@python3 dev.py fiximports
	@echo

readme:
	@echo
	@echo "******************************** Generating README ****************************"
	@echo
	@python3 generate_readme.py
	@echo

coverage:
	@echo
	@echo "******************************** Test Coverage ********************************"
	@echo
	@coverage run run.py tests
	@coverage xml
	@coverage report
	@echo

# Watch jsx files for changes and rebuild dist.js constantly while developing.
watch:
	npm run watch

# Make a branch based off of current (remote) master with all your local changes preserved (but not added).
branch:
	@if test "$(BRANCH)" = ""; then echo 'Usage: make branch BRANCH=branchname'; exit 1; fi
	@git stash -a && git clean -fxd && git checkout master && git pull && git checkout -b $(BRANCH) && git stash pop || ${MAKE} popclean

# If you try and git stash and then git stash pop when decksite is running locally you get in a mess.
# This cleans up for you.
popclean:
	@git stash pop 2>&1 | grep already | cut -d' ' -f1 | xargs rm && git stash pop
