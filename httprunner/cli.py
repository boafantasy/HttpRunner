import argparse
import multiprocessing
import os
import sys
import unittest
from collections import OrderedDict

from httprunner import __version__ as hrun_version
from httprunner import logger
from httprunner.exception import TestcaseNotFound
from httprunner.task import Result, TaskSuite
from httprunner.utils import create_scaffold, print_output, string_type
from pyunitreport import __version__ as pyu_version
from pyunitreport import HTMLTestRunner


def run_suite_path(path, mapping=None, runner=None):
    """ run suite with YAML/JSON file path
    @params:
        - path: testset path
        - mapping: passed in variables mapping, it will override variables in config block
        - runner: HTMLTestRunner() or TextTestRunner()
    """
    try:
        mapping = mapping or {}
        task_suite = TaskSuite(path, mapping)
    except TestcaseNotFound:
        sys.exit(1)

    test_runner = runner or unittest.TextTestRunner()
    result = test_runner.run(task_suite)

    output = {}
    for task in task_suite.tasks:
        output.update(task.output)

    return Result(result, output)

def main_hrun():
    """ API test: parse command line options and run commands.
    """
    parser = argparse.ArgumentParser(
        description='HTTP test runner, not just about api test and load test.')
    parser.add_argument(
        '-V', '--version', dest='version', action='store_true',
        help="show version")
    parser.add_argument(
        'testset_paths', nargs='*',
        help="testset file path")
    parser.add_argument(
        '--log-level', default='INFO',
        help="Specify logging level, default is INFO.")
    parser.add_argument(
        '--failfast', action='store_true', default=False,
        help="Stop the test run on the first error or failure.")
    parser.add_argument(
        '--startproject',
        help="Specify new project name.")

    args = parser.parse_args()
    logger.setup_logger(args.log_level)

    if args.version:
        logger.color_print("HttpRunner version: {}".format(hrun_version), "GREEN")
        logger.color_print("PyUnitReport version: {}".format(pyu_version), "GREEN")
        exit(0)

    project_name = args.startproject
    if project_name:
        project_path = os.path.join(os.getcwd(), project_name)
        create_scaffold(project_path)
        exit(0)

    kwargs = {
        "output": os.path.join(os.getcwd(), "reports"),
        "failfast": args.failfast
    }
    test_runner = HTMLTestRunner(**kwargs)
    result = run_suite_path(args.testset_paths, {}, test_runner)
    print_output(result.output)

    return 0 if result.success else 1

def main_locust():
    """ Performance test with locust: parse command line options and run commands.
    """
    logger.setup_logger("INFO")

    try:
        from httprunner import locusts
    except ImportError:
        msg = "Locust is not installed, install first and try again.\n"
        msg += "install command: pip install locustio"
        logger.log_warning(msg)
        exit(1)

    sys.argv[0] = 'locust'
    if len(sys.argv) == 1:
        sys.argv.extend(["-h"])

    if sys.argv[1] in ["-h", "--help", "-V", "--version"]:
        locusts.main()
        sys.exit(0)

    try:
        testcase_index = sys.argv.index('-f') + 1
        assert testcase_index < len(sys.argv)
    except (ValueError, AssertionError):
        logger.log_error("Testcase file is not specified, exit.")
        sys.exit(1)

    testcase_file_path = sys.argv[testcase_index]
    sys.argv[testcase_index] = locusts.parse_locustfile(testcase_file_path)

    if "--cpu-cores" in sys.argv:
        """ locusts -f locustfile.py --cpu-cores 4
        """
        if "--no-web" in sys.argv:
            logger.log_error("conflict parameter args: --cpu-cores & --no-web. \nexit.")
            sys.exit(1)

        cpu_cores_index = sys.argv.index('--cpu-cores')

        cpu_cores_num_index = cpu_cores_index + 1

        if cpu_cores_num_index >= len(sys.argv):
            """ do not specify cpu cores explicitly
                locusts -f locustfile.py --cpu-cores
            """
            cpu_cores_num_value = multiprocessing.cpu_count()
            logger.log_warning("cpu cores number not specified, use {} by default.".format(cpu_cores_num_value))
        else:
            try:
                """ locusts -f locustfile.py --cpu-cores 4 """
                cpu_cores_num_value = int(sys.argv[cpu_cores_num_index])
                sys.argv.pop(cpu_cores_num_index)
            except ValueError:
                """ locusts -f locustfile.py --cpu-cores -P 8888 """
                cpu_cores_num_value = multiprocessing.cpu_count()
                logger.log_warning("cpu cores number not specified, use {} by default.".format(cpu_cores_num_value))

        sys.argv.pop(cpu_cores_index)
        locusts.run_locusts_on_cpu_cores(sys.argv, cpu_cores_num_value)
    else:
        locusts.main()
