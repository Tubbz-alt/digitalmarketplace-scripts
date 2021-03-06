#!/usr/bin/env python
"""Export supplier information for a particular framework for evaluation

This can only be run *after* the on_framework flag has been set (e.g. by running mark-definite-framework-results.py)

Produces three files;
 - successful.csv containing suppliers that submitted at least one valid service and answered
   all mandatory and discretionary declaration questions correctly.
 - failed.csv containing suppliers that either failed to submit any valid services or answered
   some of the mandatory declaration questions incorrectly.
 - discretionary.csv containing suppliers that submitted at least one valid service and answered
   all mandatory declaration questions correctly but answered some discretionary questions
   incorrectly.

Usage:
    scripts/framework-applications/export-framework-results-reasons.py [-h] <stage> <framework_slug> <content_path>
        <output_dir> <declaration_schema_path> [<supplier_id_file>][-e <excluded_supplier_ids>]

Options:
    -h --help
"""
import json
from multiprocessing.pool import ThreadPool
import sys
sys.path.insert(0, '.')

from docopt import docopt
from dmscripts.helpers.auth_helpers import get_auth_token
from dmscripts.helpers.supplier_data_helpers import get_supplier_ids_from_file
from dmscripts.export_framework_results_reasons import export_suppliers
from dmapiclient import DataAPIClient
from dmcontent.content_loader import ContentLoader
from dmutils.env_helpers import get_api_endpoint_from_stage


if __name__ == '__main__':
    args = docopt(__doc__)

    client = DataAPIClient(get_api_endpoint_from_stage(args['<stage>']), get_auth_token('api', args['<stage>']))
    content_loader = ContentLoader(args['<content_path>'])

    declaration_definite_pass_schema = json.load(open(args["<declaration_schema_path>"], "r"))
    declaration_discretionary_pass_schema = (declaration_definite_pass_schema.get("definitions") or {}).get("baseline")

    supplier_id_file = args['<supplier_id_file>']
    supplier_ids = get_supplier_ids_from_file(supplier_id_file)
    # exclude suppliers with IDs the executioner defined
    if args['<excluded_supplier_ids>'] is not None and supplier_ids is not None:
        supplier_ids = list(set(supplier_ids) - set([int(n) for n in args['<excluded_supplier_ids>'].split(',')]))

    pool = ThreadPool(3)

    export_suppliers(
        client,
        args['<framework_slug>'],
        content_loader,
        args['<output_dir>'],
        declaration_definite_pass_schema,
        declaration_discretionary_pass_schema,
        supplier_ids,
        map_impl=pool.imap,
    )
