# Copyright 2019 Open Source Robotics Foundation
# Licensed under the Apache License, version 2.0

from colcon_core.event.job import JobEnded
from colcon_core.event_handler import EventHandlerExtensionPoint
from colcon_core.location import get_log_path
from colcon_core.logging import colcon_logger
from colcon_core.plugin_system import satisfies_version
from colcon_output.event_handler.log import STDOUT_STDERR_LOG_FILENAME
from colcon_sanitizer_reports.sanitizer_log_parser import SanitizerLogParser

logger = colcon_logger.getChild(__name__)


class SanitizerReportEventHandler(EventHandlerExtensionPoint):
    """Generate a report of all Sanitizer ERRORs and WARNINGs."""

    ENABLED_BY_DEFAULT: bool = False

    def __init__(self) -> None:
        super().__init__()
        satisfies_version(EventHandlerExtensionPoint.EXTENSION_POINT_VERSION, '^1.0')
        self.enabled: bool = SanitizerReportEventHandler.ENABLED_BY_DEFAULT
        self._log_parser: SanitizerLogParser = SanitizerLogParser()

    def __call__(self, event) -> None:
        data = event[0]
        logger.debug('Received %s event', data.__class__.__name__)

        if isinstance(data, JobEnded):
            self._handle(event)

    def _handle(self, event) -> None:
        job: JobEnded = event[1]
        self._log_parser.set_package(job.identifier)

        try:
            log_f = get_log_path() / job.identifier / STDOUT_STDERR_LOG_FILENAME
            with open(log_f, 'r') as in_file:
                for line in in_file:
                    self._log_parser.add_line(line)
        except IOError:
            logger.info('Could not open sanitizer error log file')

        with open('sanitizer_report.csv', 'w') as report_csv_f_out:
            report_csv_f_out.write(self._log_parser.csv)
