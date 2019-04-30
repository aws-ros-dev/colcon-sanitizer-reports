# Copyright 2019 Open Source Robotics Foundation
# Licensed under the Apache License, version 2.0

import re
from typing import Tuple


# Key comes from a line of ros2 code and matches the following pattern.
_FIND_KEY_REGEX = re.compile(r'^\s*#\d+ (0x[\da-f]+ in|)\s*(?P<key>.*/ros2.*)\s*$')

# Parts of a key that are changeable between otherwise identical stack trace can be found and masked
# with the following pattern.
_FIND_KEY_SUB_REGEX = re.compile(r'0x[\da-f]+')


class SanitizerSectionPartStackTrace:
    """Parses key from stack trace lines of a single sanitizer section part stack trace.

    A sanitizer section part stack trace is a group of contiguous lines in a sanitizer section part
    that make a typical stack trace.

    Examples from sanitizer output include:
        ==5584==ERROR: LeakSanitizer: detected memory leaks

        Direct leak of 64 byte(s) in 1 object(s) allocated from:
            #0 in operator new(unsigned long) (/usr/lib/x86_64-linux-gnu/libasan.so)
            #1 in rclcpp::NodeOptions::get_rcl_node_options() const (/ros2/rclcpp/lib/librclcpp.so)
            <snip stack trace lines 2-13>
            #14 in main (/ros2/test_communication/test_publisher_subscriber_cpp)
            #15 in __libc_start_main (/lib/x86_64-linux-gnu/libc.so)

        SUMMARY: AddressSanitizer: 64 byte(s) leaked in 1 allocation(s).

    This examples shows a stack trace with fifteen lines.

    After initialization, SanitizerSectionPartStackTrace includes the following data member.

    key:
        This is the first line in the stack trace that comes from ros2 code (#1 in the example
        above). Some information is masked or omitted in the key so that keys of multiple stack
        traces that are reproductions of each other are guaranteed to match.
    """

    key: str

    def __init__(self, lines: Tuple[str]) -> None:

        key = None
        for line in lines:
            match = re.match(_FIND_KEY_REGEX, line)
            if match is not None:
                key = re.sub(_FIND_KEY_SUB_REGEX, '0xX', match.groupdict()['key'])
                break

        assert key is not None, 'Could not find key in given stack trace lines.'

        self.key = key
