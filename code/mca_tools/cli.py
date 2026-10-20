"""Lightweight entry points and validated interactive/automated settings."""

import argparse
import math
import os
import sys
from pathlib import Path

from . import package_version
from .config import ConfigurationError, load_folders


def parser_for(command):
    parser = argparse.ArgumentParser(prog=command)
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {package_version()}"
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        type=Path,
        help="JSON with paths_to_files (relative paths use the JSON directory)",
    )
    if command == "shg2_intden_assay":
        parser.add_argument(
            "--input-source",
            choices=("export", "tiff"),
            help="Continue an MCA LIF export or analyze independent TIFF inputs",
        )
        parser.add_argument("--projection", choices=("max", "sum"))
        parser.add_argument("--threshold-mode", choices=("auto", "manual"))
        parser.add_argument(
            "--threshold",
            type=float,
            nargs="+",
            metavar="BOUND",
            help="Manual lower [upper] threshold; upper defaults to infinity",
        )
        parser.add_argument(
            "--channel",
            type=int,
            help="Exported channel folder (export mode only; default: 1)",
        )
        parser.add_argument(
            "--yes", action="store_true", help="Skip the start confirmation"
        )
        parser.add_argument(
            "--allow-partial-export",
            action="store_true",
            help="Allow audited files from successful LIF inputs in a PARTIAL export",
        )
        parser.add_argument(
            "--allow-legacy-export",
            action="store_true",
            help="Explicitly allow old exports without completion metadata",
        )
    return parser


def validate_threshold(values):
    if len(values) not in (1, 2):
        raise ConfigurationError("Supply one or two threshold bounds")
    lower, upper = values[0], values[1] if len(values) == 2 else float("inf")
    if not math.isfinite(lower) or math.isnan(upper) or upper < lower:
        raise ConfigurationError(
            "Threshold lower must be finite and upper must be >= lower"
        )
    return lower, upper


def ask(question, choices=None, default=None):
    if not sys.stdin.isatty():
        raise ConfigurationError(
            "Noninteractive input requires --projection, threshold settings and --yes"
        )
    while True:
        value = input(question + " [q cancels]: ").strip().lower()
        if value == "q":
            raise KeyboardInterrupt
        if not value and default is not None:
            return default
        if choices is None or value in choices:
            return value
        print("Invalid choice. Please try again.")


def analysis_settings(args):
    if args.input_source is None:
        if not sys.stdin.isatty():
            raise ConfigurationError(
                "Noninteractive analysis requires --input-source export or tiff"
            )
        choice = ask(
            "Input source: 1/export (continue LIF export) or 2/tiff (independent TIFF)",
            {"1", "2", "export", "tiff"},
        )
        args.input_source = "export" if choice in {"1", "export"} else "tiff"
    if args.input_source == "tiff" and (
        args.channel is not None
        or args.allow_partial_export
        or args.allow_legacy_export
    ):
        raise ConfigurationError(
            "--channel and --allow-*-export apply only to --input-source export; "
            "independent TIFFs must contain one SHG channel"
        )
    if args.input_source == "export" and args.channel is None:
        args.channel = 1
    if not sys.stdin.isatty() and (
        args.projection is None
        or (args.threshold_mode is None and args.threshold is None)
        or (args.threshold_mode == "manual" and args.threshold is None)
        or not args.yes
    ):
        raise ConfigurationError(
            "Noninteractive input requires --projection, threshold settings and --yes"
        )
    if args.projection is None:
        choice = ask("Projection: 1/max or 2/sum", {"1", "2", "max", "sum"})
        args.projection = "max" if choice in {"1", "max"} else "sum"
    if args.threshold is not None:
        args.threshold_mode = "manual"
    if args.threshold_mode is None:
        args.threshold_mode = ask(
            "Threshold: auto or manual", {"auto", "manual"}
        )
    if args.threshold_mode == "manual" and args.threshold is None:
        while True:
            try:
                lower = float(ask("Lower threshold (default: 0)", default="0"))
                upper = float(
                    ask("Upper threshold (default: inf)", default="inf")
                )
                args.threshold = validate_threshold([lower, upper])
                break
            except ValueError as error:
                print(f"Invalid threshold: {error}")
    if not args.yes and ask(
        "Start processing? yes/no", {"yes", "y", "no", "n"}
    ) not in {"yes", "y"}:
        raise KeyboardInterrupt
    return args


def launch(command, argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = parser_for(command)
    args = parser.parse_args(arguments)
    try:
        folders = load_folders(
            args.input, allow_tiff_files=command == "shg2_intden_assay"
        )
        if command == "shg2_intden_assay":
            if args.channel is not None and args.channel < 1:
                raise ConfigurationError("Channel numbers start at 1")
            if args.threshold is not None:
                if args.threshold_mode == "auto":
                    raise ConfigurationError(
                        "--threshold cannot be combined with automatic thresholding"
                    )
                args.threshold = validate_threshold(args.threshold)
        if os.environ.get("MCA_WORKER") != "1":
            from .runtime import run_command

            return run_command(command, arguments)
        if command == "shg1_lif_to_tif":
            from .lif_export import run_export

            return run_export(folders, args.input.resolve())
        args = analysis_settings(args)
        if args.input_source == "export" and any(
            not folder.is_dir() for folder in folders
        ):
            raise ConfigurationError(
                "Export mode requires original LIF folders in JSON; "
                "use --input-source tiff for individual TIFFs"
            )
        from .shg_analysis import run_analysis

        return run_analysis(folders, args)
    except (KeyboardInterrupt, EOFError):
        print("Cancelled by user.", file=sys.stderr)
        return 130
    except ConfigurationError as error:
        parser.error(str(error))
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


def lif_export(argv=None):
    return launch("shg1_lif_to_tif", argv)


def shg_analysis(argv=None):
    return launch("shg2_intden_assay", argv)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in {
        "shg1_lif_to_tif",
        "shg2_intden_assay",
    }:
        raise SystemExit("Use the installed MCA terminal commands")
    raise SystemExit(launch(sys.argv[1], sys.argv[2:]))
