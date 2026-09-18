# Build and test the eight-queens translation. See TESTING.md.
#
#   make test             compare the Python translation with the saved ATS output
#                         (needs only python3)
#   make expected         regenerate the saved ATS output in tests/expected/ (needs ATS2)
#   make run-original     compile and run the ATS original
#   make run-translation  run the Python translation
#   make clean            remove build/

PATSHOME ?= $(HOME)/.local/opt/ATS2-Postiats-gmp-0.4.2
PATSCC   := $(PATSHOME)/bin/patscc
ATSFLAGS := -DATS_MEMALLOC_LIBC
PYTHON   ?= python3

export PATSHOME
export PATH := $(PATSHOME)/bin:$(PATH)

BUILD    := build
EXPECTED := tests/expected

# A program that fails must not leave a half-written output file behind.
.DELETE_ON_ERROR:
.PHONY: test expected run-original run-translation clean check-ats

test:
	$(PYTHON) -m unittest discover -s tests -v

# Make only reaches the copy if both ATS programs exited 0, so a failed
# run never overwrites the committed expected files.
expected: $(BUILD)/queens.out $(BUILD)/cases.out
	cp $(BUILD)/queens.out $(BUILD)/cases.out $(EXPECTED)/

run-original: $(BUILD)/queens
	./$(BUILD)/queens

run-translation:
	$(PYTHON) translation/queens.py

clean:
	rm -rf $(BUILD)

check-ats:
	@test -x "$(PATSCC)" || { \
	  echo "error: patscc not found at $(PATSCC)" >&2; \
	  echo "Set PATSHOME to your ATS2 install: make expected PATSHOME=/path/to/ATS2" >&2; \
	  exit 1; }

$(BUILD):
	mkdir -p $@

# The original minus main0, so cases.dats can use its functions without the
# original file ever being edited.
$(BUILD)/queens_lib.dats: original/queens.dats | $(BUILD)
	sed '/^implement$$/,/end of \[main0\]/d' $< > $@
	@! grep -q main0 $@ || { echo "error: main0 was not removed from $@" >&2; exit 1; }

# patscc resolves #include paths and writes its generated C file relative to
# the current directory, so both programs are compiled from inside build/.
$(BUILD)/queens: original/queens.dats | check-ats $(BUILD)
	cd $(BUILD) && $(PATSCC) $(ATSFLAGS) -o queens ../original/queens.dats

$(BUILD)/cases: tests/ats/cases.dats $(BUILD)/queens_lib.dats | check-ats
	cd $(BUILD) && $(PATSCC) $(ATSFLAGS) -o cases ../tests/ats/cases.dats

$(BUILD)/%.out: $(BUILD)/%
	./$< > $@
