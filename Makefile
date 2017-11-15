.PHONY: default push test unit lint shortlint readme coverage branch popclean

# This is the first thing in the makefile so it is the default when just "make" is run
# and something else doesn't get run by accident.
default:
	@echo "Heroic doesn't get that affected by Barbs. Bogles though. Kills their creature, kills their face."

# Push your commits (safely) to the remote branch.
push:
	git pull origin master && make test && git push --set-upstream origin `git rev-parse --abbrev-ref HEAD`

# Run all unit and syntax tests.
test: unit lint

# Run unit tests.
TEST=.
unit:
	@echo
	@echo "******************************** Unit Tests ***********************************"
	@echo
	@pytest --junitxml=test_results.xml -k $(TEST) -m "not slowtest"
	@echo

# Run lint on all python files.
lint:
	@echo
	@echo "******************************** Lint *****************************************"
	@echo
	@find . -name "*.py" | grep -v .git | xargs pylint --reports=n -f parseable
	@echo

shortlint:
	@echo
	@echo "******************************** Lint *****************************************"
	@echo
	@find . -name "*.py" | grep -v .git | xargs pylint -f parseable -E
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

# Make a branch based off of current (remote) master with all your local changes preserved (but not added).
branch:
	@if test "$(BRANCH)" = ""; then echo 'Usage: make branch BRANCH=branchname'; exit 1; fi
	@git stash -a && git clean -fxd && git checkout master && git pull && git checkout -b $(BRANCH) && git stash pop || ${MAKE} popclean

# If you try and git stash and then git stash pop when decksite is running locally you get in a mess.
# This cleans up for you.
popclean:
	@git stash pop 2>&1 | grep already | cut -d' ' -f1 | xargs rm && git stash pop

