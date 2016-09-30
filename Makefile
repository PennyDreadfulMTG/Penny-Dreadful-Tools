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
unit:
	@echo
	@echo "******************************** Unit Tests ***********************************"
	@echo
	@pytest
	@echo

# Run lint on all python files.
lint:
	@echo
	@echo "******************************** Lint *****************************************"
	@echo
	@find . -name "*.py" | xargs pylint
	@echo
