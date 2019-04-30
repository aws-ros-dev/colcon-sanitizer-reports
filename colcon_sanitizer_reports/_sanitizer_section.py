# Copyright 2019 Open Source Robotics Foundation
# Licensed under the Apache License, version 2.0

import re
from typing import List, Tuple

from colcon_sanitizer_reports._sanitizer_section_part import SanitizerSectionPart


# Error name for the sanitizer section is in the header line and matches the following pattern.
_FIND_ERROR_NAME_REGEX = re.compile(r'^.*Sanitizer: (?P<error_name>.+?)( \(| 0x[\da-f]+|\s*$)')

# Section parts begin with non-indented lines and match the following pattern.
_FIND_SECTION_PART_BEGIN_REGEX = re.compile(r'^\S.*$')


class SanitizerSection:
    """Parses error name and sub section parts from log lines of a single sanitizer section.

    A sanitizer section includes all the sanitizer output lines including

        1. A single Error/Warning header line
        2. Many log lines, the Contents of the error/warning including stack traces.
        3. A single SUMMARY line

    Examples from sanitizer output include:
        WARNING: ThreadSanitizer: lock-order-inversion (potential deadlock) (pid=26542)
        <snip ThreadSanitizer warning output contents>
        SUMMARY: ThreadSanitizer: lock-order-inversion (potential deadlock)
    or
        ==5054==ERROR: AddressSanitizer: SEGV on unknown address 0x60304d80008f
        <snip AddressSanitizer error output contents>
        SUMMARY: AddressSanitizer: SEGV (/lib/x86_64-linux-gnu/libc.so.6+0x18e5a0)

    SanitizerSection is initialized with a tuple of all lines from a sanitizer output section
    including the header, contents, and summary.

    After initialization, SanitizerSection includes two data members.

    error_name: parsed from the header. From the examples above, this would be
        'lock-order-inversion' or 'SEGV on unknown address'.

    parts:
        Tuple of SanitizerSectionParts. See SanitizerSectionPart for definition of a section part.
    """

    error_name: str
    parts: Tuple[SanitizerSectionPart]

    def __init__(self, *, lines: Tuple[str]) -> None:
        # Section error name comes after 'Sanitizer: ', and before any open paren or hex number.
        self.error_name = re.match(_FIND_ERROR_NAME_REGEX, lines[0]).groupdict()['error_name']

        # Divide into parts. Subsections begin with a line that is not indented.
        part_lines: List[str] = []
        sub_sections: List[SanitizerSectionPart] = []
        for line in lines:
            # Check if this the beginning of a new part and we collected lines for a previous part.
            # If so, create the previous part and start collecting for the new part.
            match = re.match(_FIND_SECTION_PART_BEGIN_REGEX, line)
            if match is not None and part_lines:
                sub_sections.append(
                    SanitizerSectionPart(error_name=self.error_name, lines=tuple(part_lines))
                )
                part_lines = []

            part_lines.append(line)
        else:
            sub_sections.append(
                SanitizerSectionPart(error_name=self.error_name, lines=tuple(part_lines))
            )

        self.parts = tuple(sub_sections)