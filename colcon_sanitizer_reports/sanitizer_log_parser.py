# Copyright 2019 Open Source Robotics Foundation
# Licensed under the Apache License, version 2.0

from collections import defaultdict
import csv
from io import StringIO
import re
from typing import Dict, List, NamedTuple, Optional

from colcon_sanitizer_reports._sanitizer_section import SanitizerSection

# The start line of a section can be found with the following regex. Additionally, any prefix that
# is prepended by the logging system can be extracted and be used to lstrip following section lines.
_FIND_SECTION_START_LINE_REGEX = \
    re.compile(r'^(?P<prefix>.*?)(==\d+==|)(WARNING|ERROR):.*Sanitizer:.*$')

# The end line of a section can be found with the following regex. Additionally, any prefix that is
# prepended by the logging system can be extracted and be used to match the common prefix of the
# section to which the end line belongs.
_FIND_SECTION_END_LINE_REGEX = re.compile(r'^(?P<prefix>.*?)(SUMMARY: .*Sanitizer: .*)$')


class SanitizerLogParserOutputPrimaryKey(NamedTuple):
    """SanitizerLogParser report output is keyed on these fields.

    This is the primary key of the report. Each unique combination of these fields is reported on
    its own line and no two output lines will have a duplicate combination of these fields.

    After initialization, SanitizerLogParserOutputPrimaryKey includes the following data members.

    package:
        Name of the ros2 package where the error occurred.

    error_name:
        Name of the sanitizer error (such as "data race", "lock-order-inversion", etc). See
        SanitizerSection for more details.

    stack_trace_key:
        The key of a significant stack trace. Note that a single sanitizer error/warning section may
        have multiple significant stack traces, resulting in multiple keys and thus, multiple
        SanitizerLogParserOutputPrimaryKeys. See SanitizerSectionPart and
        SanitizerSectionPartStackTrace for more details.
    """

    package: str
    error_name: str
    stack_trace_key: str


class SanitizerLogParser:
    """Parses sanitizer error and warning sections from a log and generates a summary report.

    The parser works with the output of "colcon test" and reports information about all sanitizer
    (eg. AddressSanitizer or ThreadSanitizer) error and warning output. Every sanitizer error and
    warning occurs during tests for some ros2 package, has a specific error name, and has one or
    more significant stack traces that are helpful for determining the root cause of the error or
    warning.

    Lines from "colcon test" output should be added to the parser one at a time with the add_line()
    method. When finished, the report can be access from the csv property.

    CSV output columns are "package,error_name,stack_trace_key,count". Package, error_name, and
    stack_trace_key columns make up the primary key for CSV output. See SanitizerLogParserOutputPrimaryKey for more
    details about the primary key.

    CSV output additional columns include:

    count:
        The count of times the fields from the primary key occur while parsing the log.
    """

    def __init__(self) -> None:
        # Holds count of errors seen for each output key (.
        self._count_by_output_primary_key = defaultdict(int)

        # Current package output that is being parsed
        self._package: Optional[str] = None

        # We keep lines for partially-gathered sanitizer sections here. Incoming lines that match
        # one of the find_line_regexes is appended to the associated list of lines.
        # noinspection PyUnresolvedReferences
        self._lines_by_find_line_regex: Dict[re.Pattern, List[str]] = {}

    @property
    def csv(self) -> str:
        """Return a csv representation of reported error/warnings."""
        csv_f_out = StringIO()
        writer = csv.writer(csv_f_out)
        writer.writerow([*SanitizerLogParserOutputPrimaryKey._fields, 'count'])
        for output_key, count in self._count_by_output_primary_key.items():
            writer.writerow([*output_key, count])

        return csv_f_out.getvalue()

    def set_package(self, package: Optional[str]) -> None:
        self._package = package

    def add_line(self, line: str) -> None:
        line = line.rstrip()

        # If we have a sanitizer section starting line, start gathering lines for it.
        match = re.match(_FIND_SECTION_START_LINE_REGEX, line)
        if match is not None:
            # Future lines for this new sanitizer section are sometimes interleaved with unrelated
            # log lines due to multi-threaded logging. The log lines we care about will have the
            # same prefix, so they will match the following pattern with the prefix included.
            prefix = match.groupdict()['prefix']
            find_line_regex = re.compile(r'^{prefix}(?P<line>.*)$'.format(prefix=re.escape(prefix)))
            self._lines_by_find_line_regex[find_line_regex] = []

        # If this line belongs to one of the sections we're currently building, append it to lines
        # for that section.
        for find_line_regex, lines in self._lines_by_find_line_regex.items():
            match = re.match(find_line_regex, line)
            if match is not None:
                lines.append(match.groupdict()['line'])

                # If this is the last line of a section, create the section and stop gathering lines
                # for it.
                match = re.match(_FIND_SECTION_END_LINE_REGEX, line)
                if match is not None:
                    section = SanitizerSection(lines=tuple(lines))
                    for part in section.parts:
                        for relevant_stack_trace in part.relevant_stack_traces:
                            output_primary_key = SanitizerLogParserOutputPrimaryKey(
                                self._package, section.error_name, relevant_stack_trace.key
                            )
                            self._count_by_output_primary_key[output_primary_key] += 1
                    del self._lines_by_find_line_regex[find_line_regex]

                break
