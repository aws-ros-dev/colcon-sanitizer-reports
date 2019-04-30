# Copyright 2019 Open Source Robotics Foundation
# Licensed under the Apache License, version 2.0

from csv import DictReader
import os
from typing import Dict, Optional, Tuple

from colcon_sanitizer_reports.sanitizer_log_parser import SanitizerLogParser
import pytest

# Directory names of resources in test/resources. Directories should include 'input.log' and
# 'expected_output.csv'.
_RESOURCE_NAMES = (
    'data_race_and_lock_order_inversion_interleaved_output',
    'data_race_different_keys',
    'detected_memory_leaks_multiple_subsections_direct_and_indirect_leaks',
    'lock_order_inversion_same_key',
    'no_errors',
    'segv',
)


class SanitizerLogParserFixture:
    def __init__(self, resource_name: str) -> None:
        self.resource_name = resource_name
        self._sanitizer_log_parser: Optional[SanitizerLogParser] = None

    @property
    def resource_path(self) -> str:
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'resources', self.resource_name
        )

    @property
    def input_log_path(self) -> str:
        return os.path.join(self.resource_path, 'input.log')

    @property
    def expected_output_csv_path(self) -> str:
        return os.path.join(self.resource_path, 'expected_output.csv')

    @property
    def sanitizer_log_parser(self) -> SanitizerLogParser:
        if self._sanitizer_log_parser is None:
            parser = SanitizerLogParser()
            parser.set_package(self.resource_name)
            with open(self.input_log_path, 'r') as input_log_f_in:
                for line in input_log_f_in.readlines():
                    parser.add_line(line)

            self._sanitizer_log_parser = parser
            parser.set_package(None)

        return self._sanitizer_log_parser

    @property
    def report_csv(self) -> DictReader:
        return DictReader(self.sanitizer_log_parser.csv.split('\n'))

    @property
    def expected_csv(self) -> DictReader:
        with open(self.expected_output_csv_path, 'r') as expected_output_csv_f_in:
            return DictReader(expected_output_csv_f_in.read().split('\n'))


@pytest.fixture(params=_RESOURCE_NAMES)
def sanitizer_log_parser_fixture(request) -> SanitizerLogParserFixture:
    return SanitizerLogParserFixture(request.param)


def test_csv_has_output(sanitizer_log_parser_fixture) -> None:
    if sanitizer_log_parser_fixture.resource_name == 'no_errors':
        assert len(list(sanitizer_log_parser_fixture.report_csv)) == 0
    else:
        assert len(list(sanitizer_log_parser_fixture.report_csv)) > 0


def test_csv_has_expected_line_count(sanitizer_log_parser_fixture) -> None:
    assert len(list(sanitizer_log_parser_fixture.report_csv)) == \
           len(list(sanitizer_log_parser_fixture.expected_csv))


def test_csv_has_expected_lines(sanitizer_log_parser_fixture) -> None:
    def make_key(line: Dict[str, str]) -> Tuple[str, ...]:
        return tuple(line.items())

    expected_line_by_key = {
        make_key(line): line for line in sanitizer_log_parser_fixture.expected_csv
    }

    for line in sanitizer_log_parser_fixture.report_csv:
        assert line == expected_line_by_key.pop(make_key(line))
