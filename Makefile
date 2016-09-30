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
# Run an individual test or directory with make unit FILE=path/to/test
unit:
	@echo
	@echo "******************************** Unit Tests ***********************************"
	@echo
	@pytest $(FILE)
	@echo

# Run lint on all python files.
# Run on a single file with $ make lint FILE=greppattern
lint:
	@echo
	@echo "******************************** Lint *****************************************"
	@echo
	@find . -name "*.py" | xargs pylint
	@echo
