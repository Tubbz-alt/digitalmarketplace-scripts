#!/usr/bin/env python
"""Rename registration country from 'gb' to 'country:GB'

We currently only have one country code in the database and that's for suppliers who are registered in the UK. It's
'gb'. We're going start using the country picker as supplied by registers, and the country codes are stored in a
different format. This script is to migrate our existing data to fall in line with the new country codes.

See: https://trello.com/c/FeBysBI7

Usage:
    ./scripts/oneoff/rename-supplier-registered-country.py <stage> [--dry-run]
"""
import sys
sys.path.insert(0, '.')

from docopt import docopt
from dmapiclient import DataAPIClient, HTTPError
from dmscripts.helpers.auth_helpers import get_auth_token
from dmutils.env_helpers import get_api_endpoint_from_stage

OLD_COUNTRY = "gb"
NEW_COUNTRY = "country:GB"


def rename_country(client, dry_run):
    success_counter = 0
    failure_counter = 0
    for supplier in client.find_suppliers_iter():
        if supplier.get('registrationCountry') == OLD_COUNTRY:
            if not dry_run:
                try:
                    client.update_supplier(
                        supplier['id'],
                        {'registrationCountry': NEW_COUNTRY},
                        'rename supplier registered country script',
                    )
                    success_counter += 1
                except HTTPError as e:
                    print("Error updating supplier {}: {}".format(supplier['id'], e.message))
                    failure_counter += 0

    print("{}Succssfully updated {}".format('Dry run - ' if dry_run else '', success_counter))
    print("{}Failed to update {}".format('Dry run - ' if dry_run else '', failure_counter))


if __name__ == '__main__':
    arguments = docopt(__doc__)

    stage = arguments['<stage>']
    dry_run = arguments['--dry-run']
    api_url = get_api_endpoint_from_stage(stage)

    rename_country(DataAPIClient(api_url, get_auth_token('api', stage)), dry_run)
