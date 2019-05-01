# Copyright 2019 Open Source Robotics Foundation
# Licensed under the Apache License, version 2.0

from collections import ChainMap, defaultdict
import re
from typing import List, Optional, Tuple

from colcon_sanitizer_reports._sanitizer_section_part_stack_trace import \
    SanitizerSectionPartStackTrace


_FIND_RELEVANT_STACK_TRACE_BEGIN_REGEXES_BY_ERROR_NAME = ChainMap({
    # There are two relevant stack traces involved in a "data race" section part. Their headers
    # match the following patterns.
    'data race': (
        re.compile(r'^\s+(Read|Write) of size \d+ at 0x[\da-f]+ .*$'),
        re.compile(r'^\s+Previous (read|write) of size \d+ at 0x[\da-f]+ .*$'),
    ),
    # There is one relevant stack trace in a "detected memory leaks" section part. Its header
    # matches the following pattern.
    'detected memory leaks': (
        re.compile(r'^Direct leak of \d+ byte\(s\) in \d+ object\(s\) allocated from:$'),
    ),
    # There are two relevant stack traces involved in one "lock-order-inversion" error section part.
    # Both of their headers match the same pattern.
    'lock-order-inversion': (
        re.compile(r'^\s+Mutex M\d+ acquired here while holding mutex M\d+ in .*$'),
        re.compile(r'^\s+Mutex M\d+ acquired here while holding mutex M\d+ in .*$'),
    ),
    # Remaining sanitizer errors have the only/most relevant stack trace first in a section part, so
    # we place no restrictions on the pattern of the header. We just find the first stack trace.
}, defaultdict(lambda: (re.compile(r'^.*$'),)))

# Stack trace lines follow a "stack trace begin" line and match the following pattern.
_FIND_STACK_TRACE_LINE_REGEX = re.compile(r'^\s*#\d+\s+.*$')


class SanitizerSectionPart:
    """Parses relevant stack traces from log lines of a single sanitizer section part.

    A sanitizer section part is a group of contiguous lines in a sanitizer section starting with a
    single non-indented line followed by all the indented lines until the next non-indented line.

    Examples from sanitizer output include:
        WARNING: ThreadSanitizer: lock-order-inversion (potential deadlock) (pid=26542)
          Cycle in lock order graph: M28001314164204480 <snip>

          Mutex M3363081369841140 acquired here while holding mutex M2800131416420448 in thread T5:
            <snip relevant stack trace>

          Mutex M2800131416420448 acquired here while holding mutex M3363081369841140 in thread T5:
            <snip relevant stack trace>

          Thread T5 (tid=26553, running) created by main thread at:
            <snip irrelevant stack trace>

        SUMMARY: ThreadSanitizer: lock-order-inversion (potential deadlock) <snip>
    or
        ==5504==ERROR: LeakSanitizer: detected memory leaks

        Direct leak of 1 byte(s) in 1 object(s) allocated from:
            <snip relevant stack trace>

        Indirect leak of 1 byte(s) in 1 object(s) allocated from:
            <snip irrelevant stack trace>

        SUMMARY: AddressSanitizer: 554924 byte(s) leaked in 6385 allocation(s).

    The first example has two section parts. Part one starts with the lock-order-inversion line and
    includes all the indented lines until the summary line. It includes two relevant and one
    irrelevant stack traces to report. Part two is the summary line.

    The second example has four section parts. Part one is just the summary line. Parts two starts
    with the non-indented "Direct leak" line and includes the following stack trace that is relevant
    to report. Part three starts with the non-indented "Indirect leak" line and includes the
    following stack trace that is irrelevant to report. The final part is the summary line.

    See _FIND_RELEVANT_STACK_TRACE_BEGIN_REGEXES_BY_ERROR_NAME for stack trace header search
    patterns that determine which stack traces are relevant. Different error/warning names have
    different relevant stack traces.

    After initialization, SanitizerSectionPart includes the following data member.

    relevant_stack_traces:
        Tuple of all stack traces from the section part that are relevant for generating the report.
    """

    relevant_stack_traces: Tuple[SanitizerSectionPartStackTrace]

    def __init__(self, *, error_name: str, lines: Tuple[str]) -> None:

        relevant_stack_traces: List[SanitizerSectionPartStackTrace] = []
        relevant_stack_trace_lines: Optional[List[str]] = None
        find_relevant_stack_trace_begin_regexes = \
            _FIND_RELEVANT_STACK_TRACE_BEGIN_REGEXES_BY_ERROR_NAME[error_name]

        for line in lines:
            # Check if we're currently gathering lines of a relevant stack trace.
            if relevant_stack_trace_lines is not None:
                match = re.match(_FIND_STACK_TRACE_LINE_REGEX, line)
                if match is not None:
                    relevant_stack_trace_lines.append(line)
                    continue

                relevant_stack_traces.append(
                    SanitizerSectionPartStackTrace(lines=tuple(relevant_stack_trace_lines))
                )
                relevant_stack_trace_lines = None
                if len(relevant_stack_traces) == len(find_relevant_stack_trace_begin_regexes):
                    break

            find_relevant_stack_trace_begin_regex = \
                find_relevant_stack_trace_begin_regexes[len(relevant_stack_traces)]
            match = re.match(find_relevant_stack_trace_begin_regex, line)
            if match is not None:
                relevant_stack_trace_lines = []

        if relevant_stack_trace_lines:
            relevant_stack_traces.append(
                SanitizerSectionPartStackTrace(lines=tuple(relevant_stack_trace_lines))
            )

        self.relevant_stack_traces = tuple(relevant_stack_traces)
