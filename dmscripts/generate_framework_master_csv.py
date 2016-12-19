# -*- coding: utf-8 -*-
"""Class used to output a framework master csv."""
from collections import OrderedDict

from dmscripts.dmscripts_csv import GenerateCSVFromAPI


class GenerateMasterCSV(GenerateCSVFromAPI):
    """"Generate a master csv given a framework."""

    static_fieldnames = ('supplier_id', 'supplier_dm_name', 'application_status', 'declaration_status')
    service_status_labels = OrderedDict([
        ("not-submitted", "draft"),
        ("submitted", "completed"),
        ("failed", "completed")
    ])

    def __init__(self, client, target_framework_slug):
        """Set up CSV builder with a client, framework and lot details and a placeholder for output.

        :param client: Instance of dmapiclient.data.DataAPIClient
        :param target_framework_slug: A framework slug ie 'digital-outcomes-and-specialists-2' or 'g-cloud-8'
        """
        super(GenerateMasterCSV, self).__init__(client)
        self.target_framework_slug = target_framework_slug
        self.framework = self.client.get_framework(target_framework_slug)['frameworks']
        self.lot_slugs = tuple(i['slug'] for i in self.framework['lots'])

    def get_column_name(self, service_status, lot_slug):
        """For each lot we're working out how many submitted and non-submitted services they have.
        To indicate this in the csv we have headings like 'draft_iaas, completed_iaas, draft_saas, completed_saas etc.'
        In this method, given a status 'non-submitted' and a lot_slug 'iaas' we produce the label 'draft_iaas'.
        """
        return self.service_status_labels[service_status] + '_' + lot_slug

    def _get_dynamic_field_names(self):
        """
        :return: List of strings. Dynamic field names for CSV.
        """
        dynamic_fields = []
        for lot_name in self.lot_slugs:
            for label_prefix in self.service_status_labels.keys():
                column_name = self.get_column_name(label_prefix, lot_name)
                if column_name not in dynamic_fields:
                    dynamic_fields.append(column_name)
        return dynamic_fields

    def get_fieldnames(self):
        """
        :return: List of strings. All field names for CSV.
        """
        return self.static_fieldnames + tuple(self._get_dynamic_field_names())

    def populate_output(self):
        """Method to actually populate our output placeholder."""
        self._update_with_supplier_data(self.output)

    def get_supplier_service_data(self, supplier_id):
        """Given a supplier ID return a list of dictionaries for services related to framework."""
        return self.client.find_draft_services_iter(supplier_id, framework=self.target_framework_slug)

    def get_supplier_frameworks(self):
        """Return supplier frameworks."""
        return self.client.find_framework_suppliers(self.target_framework_slug)['supplierFrameworks']

    def _tmp_update_with_application_status(self, supplier_dict, sf):
        """TODO: Temporary method to calculate application script side until we get it from the api.

        To remove this method remove the method, the single call in _update_with_supplier_data and
        add in another way to get the application status, preferably from the api.
        """
        try:
            declaration_complete = sf['declaration'].get('status') == 'complete'
        except (KeyError, AttributeError):
            declaration_complete = False
        if declaration_complete:
            completed_service_keys = filter(lambda i: i.startswith('completed_'), supplier_dict.keys())
            completed_service = any(supplier_dict[k] for k in completed_service_keys)
            if completed_service:
                supplier_dict['application_status'] = 'application'
        if not declaration_complete or not completed_service:
            supplier_dict['application_status'] = 'no_application'

    def _update_with_supplier_data(self, output):
        """Update self.output with supplier data."""
        supplier_frameworks = self.get_supplier_frameworks()
        field_names = self.get_fieldnames()
        for sf in supplier_frameworks:
            # This bit takes care of the columns in static_fieldnames.
            supplier_id = sf['supplierId']
            declaration = sf['declaration']['status'] if sf['declaration'] else ''
            supplier_info = [supplier_id, sf['supplierName'], '', declaration]
            # This creates placeholders for the dynamic lot fieldnames.
            lot_placeholders = [0 for i in self._get_dynamic_field_names()]
            supplier_dict = dict(zip(field_names, supplier_info + lot_placeholders))
            # Get service data and process dynamic lot values
            service_data = self.get_supplier_service_data(supplier_id)
            for service in service_data:
                # Calculate the status of each service an what lot it is in then +1 to the corresponding column.
                column_name = self.get_column_name(service['status'], service['lotSlug'])
                supplier_dict[column_name] += 1
            self._tmp_update_with_application_status(supplier_dict, sf)
            output.append(supplier_dict)