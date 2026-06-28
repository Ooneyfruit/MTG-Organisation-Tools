import os
import sys
import unittest

def run_all_tests():
    # Find the current script's directory
    suite_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Ensure workspace parent directory is in sys.path
    workspace_dir = os.path.abspath(os.path.join(suite_dir, ".."))
    if workspace_dir not in sys.path:
        sys.path.insert(0, workspace_dir)
        
    print("=" * 80)
    print("                  MTG WORKSPACE MASTER TEST RUNNER")
    print("=" * 80)
    print(f"Suite Directory: {suite_dir}")
    print(f"Workspace Root:  {workspace_dir}\n")

    # Discover and load all test suites in the zzz_testing_suite directory
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=suite_dir, pattern="*.py")

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 80)
    print("                                TEST SUMMARY")
    print("=" * 80)
    print(f"Ran:     {result.testsRun} test(s)")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors:   {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")
        sys.exit(0)
    else:
        print("\n>>> TEST SUITE FAILED! <<<")
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
