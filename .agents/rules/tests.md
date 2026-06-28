# Centralized Centralized Regression Testing Rules

This workspace centralizes all tests to guarantee code changes don't break existing parsing, sorting, pricing, or importing logic.

## Centralized Centralized Regression Testing Protocol

1. **Test Location**: All test scripts must be located in [yyy_testing_suite/](file:///C:/Users/dougl/Documents/Code/_MTG/yyy_testing_suite/). Do not place test scripts or test data in the individual feature directories.
2. **Auto-Discovery**:
   - The master test runner is [run_all_tests.py](file:///C:/Users/dougl/Documents/Code/_MTG/yyy_testing_suite/run_all_tests.py).
   - Any new test file must be named with the `test_` prefix (e.g. `test_price_checker.py`) or end with `_test.py` to be automatically discovered by the runner.
3. **Execution**:
   - Run the master test runner using `python run_all_tests.py` from within `yyy_testing_suite/` to execute the full test suite.
4. **Mocking External APIs**:
   - Always mock out network calls to Scryfall or other external APIs inside the tests. Use local cache simulation or Python's `unittest.mock` to ensure tests can run completely offline and fast.
