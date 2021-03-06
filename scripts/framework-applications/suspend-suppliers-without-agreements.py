#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
After a framework goes live, suppliers have a short period (usually 2 weeks) within which they must return their
signed framework agreement. If they have not returned their agreement, it cannot be countersigned by CCS and the
supplier will be unable to sell their services. We should therefore temporarily suspend the supplier's services
so that buyers won't see them in search results (G-Cloud) or the supplier cannot apply to an opportunity (DOS).
Suppliers who have returned an incorrect agreement file ('on-hold') should not be suspended.

This script carries out the same action that a CCS Category user could perform in the admin, but in bulk.
In the past CCS has provided a list of supplier IDs that should be suspended, however this script can also
suspend all suppliers who have not returned a framework agreement.

Usage:
    scripts/framework-applications/suspend-suppliers-without-agreements.py
        [-v...] [options]
        <stage> <framework> <output_dir>
        [--supplier-id=<id>... | --supplier-ids-from=<file>]
    scripts/framework-applications/suspend-suppliers-without-agreements.py (-h | --help)

Options:
    <stage>                     Environment to run script against.
    <framework>                 Slug of framework to generate agreements for.
    <output_dir>                Output folder for list of email addresses to send notifications to.

    --supplier-id=<id>          ID of supplier to generate agreement page for.
    --supplier-ids-from=<file>  Path to file containing supplier IDs, one per line.

    -h, --help                  Show this help message

    -n, --dry-run               Run script without generating files.
    -v, --verbose               Show debug log messages.

    If neither `--supplier-ids-from` or `--supplier-id` are provided then
    all suppliers without framework agreements will be suspended.
"""
import csv
import sys
import pathlib

from docopt import docopt

sys.path.insert(0, '.')

from dmscripts.helpers.auth_helpers import get_auth_token
from dmscripts.helpers.logging_helpers import (
    configure_logger,
    logging,
)
from dmscripts.helpers.framework_helpers import find_suppliers_without_agreements
from dmscripts.helpers.supplier_data_helpers import get_supplier_ids_from_args

from dmapiclient import DataAPIClient
from dmutils.env_helpers import get_api_endpoint_from_stage
from dmscripts.suspend_suppliers_without_agreements import (
    suspend_supplier_services, get_all_email_addresses_for_supplier
)


if __name__ == "__main__":
    args = docopt(__doc__)

    stage = args["<stage>"]
    framework_slug = args["<framework>"]

    dry_run = args["--dry-run"]
    verbose = args["--verbose"]
    output_dir = pathlib.Path(args["<output_dir>"])
    FILENAME = f'{framework_slug}-suspended-suppliers.csv'

    logger = configure_logger({
        "dmapiclient.base": logging.WARNING,
        "framework_helpers": logging.DEBUG if verbose >= 2 else logging.WARNING,
        "script": logging.DEBUG if verbose else logging.INFO,
    })

    client = DataAPIClient(
        get_api_endpoint_from_stage(args["<stage>"]),
        get_auth_token("api", args["<stage>"]),
    )

    framework = client.get_framework(framework_slug)["frameworks"]
    # Check that the framework is in live or standstill
    if framework['status'] not in ['live', 'standstill']:
        logger.error(f"Cannot suspend services for '{framework_slug}' with status {framework['status']}")
        exit(1)

    supplier_ids = get_supplier_ids_from_args(args)
    suppliers = find_suppliers_without_agreements(client, framework_slug, supplier_ids)

    with open(output_dir / FILENAME, 'w') as csvfile:
        csv_headers = ['Supplier email', 'Supplier ID', "No. of services suspended"]

        writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(csv_headers)

        for supplier in suppliers:
            supplier_id = supplier["supplierId"]
            framework_info = client.get_supplier_framework_info(supplier_id, framework_slug)

            # Do the suspending
            suspended_service_count = suspend_supplier_services(
                client, logger, framework_slug, supplier_id, framework_info, dry_run
            )

            if suspended_service_count == 0:
                # We should have logged why already
                continue

            # Compile a list of email addresses for the supplier (to be sent via Notify) and add to the CSV
            for supplier_email in get_all_email_addresses_for_supplier(client, framework_info):
                writer.writerow([supplier_email, supplier_id, suspended_service_count])
