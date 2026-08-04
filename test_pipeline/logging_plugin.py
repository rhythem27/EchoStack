import sys
import traceback
import pytest

class FailureLoggerPlugin:
    """
    Pytest plugin that intercepts test execution failures and prints detailed,
    formatted error logs to standard output/error with error context, traceback details,
    and system status.
    """
    
    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()

        # Capture failures occurring during setup, call, or teardown phases
        if report.failed:
            self._log_test_failure(item, call, report)

    def _log_test_failure(self, item, call, report):
        sep = "=" * 80
        sub_sep = "-" * 80
        
        print(f"\n{sep}", file=sys.stderr)
        print(f" [TEST FAILURE DETECTED IN PIPELINE]", file=sys.stderr)
        print(f"{sep}", file=sys.stderr)
        print(f" Test Node ID : {item.nodeid}", file=sys.stderr)
        print(f" File Path    : {item.fspath}", file=sys.stderr)
        print(f" Test Phase   : {report.when}", file=sys.stderr)
        
        if call.excinfo:
            exc_type = call.excinfo.type.__name__ if call.excinfo.type else "UnknownException"
            exc_val = str(call.excinfo.value)
            print(f" Exception    : {exc_type}: {exc_val}", file=sys.stderr)
            
            print(f"\n{sub_sep}", file=sys.stderr)
            print(f" FAILURE TRACEBACK:", file=sys.stderr)
            print(f"{sub_sep}", file=sys.stderr)
            
            # Print formatted traceback entries
            formatted_tb = "".join(traceback.format_exception(call.excinfo.type, call.excinfo.value, call.excinfo.tb))
            print(formatted_tb, file=sys.stderr)

        # Print captured output if any exists
        if report.capstdout:
            print(f"\n{sub_sep}", file=sys.stderr)
            print(f" CAPTURED STDOUT:", file=sys.stderr)
            print(f"{sub_sep}\n{report.capstdout}", file=sys.stderr)

        if report.capstderr:
            print(f"\n{sub_sep}", file=sys.stderr)
            print(f" CAPTURED STDERR:", file=sys.stderr)
            print(f"{sub_sep}\n{report.capstderr}", file=sys.stderr)

        if hasattr(report, "longreprtext") and report.longreprtext:
            print(f"\n{sub_sep}", file=sys.stderr)
            print(f" DETAILED PYTEST ERROR REPORT:", file=sys.stderr)
            print(f"{sub_sep}\n{report.longreprtext}", file=sys.stderr)

        print(f"{sep}\n", file=sys.stderr)
