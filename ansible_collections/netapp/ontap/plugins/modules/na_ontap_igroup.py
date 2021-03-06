#!/usr/bin/python
''' this is igroup module

 (c) 2018-2019, NetApp, Inc
 # GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
'''

from __future__ import absolute_import, division, print_function

__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'certified'
}

DOCUMENTATION = '''

module: na_ontap_igroup
short_description: NetApp ONTAP iSCSI or FC igroup configuration
extends_documentation_fragment:
    - netapp.ontap.netapp.na_ontap
version_added: 2.6.0
author: NetApp Ansible Team (@carchi8py) <ng-ansibleteam@netapp.com>

description:
    - Create/Delete/Rename Igroups and Modify initiators belonging to an igroup

options:
  state:
    description:
    - Whether the specified Igroup should exist or not.
    choices: ['present', 'absent']
    type: str
    default: present

  name:
    description:
    - The name of the igroup to manage.
    required: true
    type: str

  initiator_group_type:
    description:
    - Type of the initiator group.
    - Required when C(state=present).
    choices: ['fcp', 'iscsi', 'mixed']
    type: str
    aliases: ['protocol']

  from_name:
    description:
    - Name of igroup to rename to name.
    version_added: 2.7.0
    type: str

  os_type:
    description:
    - OS type of the initiators within the group.
    type: str
    aliases: ['ostype']

  initiators:
    description:
    - List of initiators to be mapped to the igroup.
    - WWPN, WWPN Alias, or iSCSI name of Initiator to add or remove.
    - For a modify operation, this list replaces the exisiting initiators
    - This module does not add or remove specific initiator(s) in an igroup
    aliases:
    - initiator
    type: list
    elements: str

  bind_portset:
    description:
    - Name of a current portset to bind to the newly created igroup.
    type: str

  force_remove_initiator:
    description:
    -  Forcibly remove the initiator even if there are existing LUNs mapped to this initiator group.
    type: bool
    default: false
    aliases: ['allow_delete_while_mapped']

  vserver:
    description:
    - The name of the vserver to use.
    required: true
    type: str

'''

EXAMPLES = '''
    - name: Create iSCSI Igroup
      na_ontap_igroup:
        state: present
        name: ansibleIgroup3
        initiator_group_type: iscsi
        os_type: linux
        initiators: iqn.1994-05.com.redhat:scspa0395855001.rtp.openenglab.netapp.com,abc.com:redhat.com
        vserver: ansibleVServer
        hostname: "{{ netapp_hostname }}"
        username: "{{ netapp_username }}"
        password: "{{ netapp_password }}"

    - name: Create FC Igroup
      na_ontap_igroup:
        state: present
        name: ansibleIgroup4
        initiator_group_type: fcp
        os_type: linux
        initiators: 20:00:00:50:56:9f:19:82
        vserver: ansibleVServer
        hostname: "{{ netapp_hostname }}"
        username: "{{ netapp_username }}"
        password: "{{ netapp_password }}"

    - name: rename Igroup
      na_ontap_igroup:
        state: present
        from_name: ansibleIgroup3
        name: testexamplenewname
        initiator_group_type: iscsi
        os_type: linux
        initiators: iqn.1994-05.com.redhat:scspa0395855001.rtp.openenglab.netapp.com
        vserver: ansibleVServer
        hostname: "{{ netapp_hostname }}"
        username: "{{ netapp_username }}"
        password: "{{ netapp_password }}"

    - name: Modify Igroup Initiators (replaces exisiting initiators)
      na_ontap_igroup:
        state: present
        name: ansibleIgroup3
        initiator_group_type: iscsi
        os_type: linux
        initiator: iqn.1994-05.com.redhat:scspa0395855001.rtp.openenglab.netapp.com
        vserver: ansibleVServer
        hostname: "{{ netapp_hostname }}"
        username: "{{ netapp_username }}"
        password: "{{ netapp_password }}"

    - name: Delete Igroup
      na_ontap_igroup:
        state: absent
        name: ansibleIgroup3
        vserver: ansibleVServer
        hostname: "{{ netapp_hostname }}"
        username: "{{ netapp_username }}"
        password: "{{ netapp_password }}"
'''

RETURN = '''
'''

import traceback

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native
import ansible_collections.netapp.ontap.plugins.module_utils.netapp as netapp_utils
from ansible_collections.netapp.ontap.plugins.module_utils.netapp_module import NetAppModule
from ansible_collections.netapp.ontap.plugins.module_utils.netapp import OntapRestAPI
import ansible_collections.netapp.ontap.plugins.module_utils.rest_response_helpers as rrh

HAS_NETAPP_LIB = netapp_utils.has_netapp_lib()


class NetAppOntapIgroup(object):
    """Create/Delete/Rename Igroups and Modify initiators list"""
    def __init__(self):

        self.argument_spec = netapp_utils.na_ontap_host_argument_spec()
        self.argument_spec.update(dict(
            state=dict(required=False, type='str', choices=['present', 'absent'], default='present'),
            name=dict(required=True, type='str'),
            from_name=dict(required=False, type='str', default=None),
            os_type=dict(required=False, type='str', aliases=['ostype']),
            initiator_group_type=dict(required=False, type='str',
                                      choices=['fcp', 'iscsi', 'mixed'],
                                      aliases=['protocol']),
            initiators=dict(required=False, type='list', elements='str', aliases=['initiator']),
            vserver=dict(required=True, type='str'),
            force_remove_initiator=dict(required=False, type='bool', default=False, aliases=['allow_delete_while_mapped']),
            bind_portset=dict(required=False, type='str')
        ))

        self.module = AnsibleModule(
            argument_spec=self.argument_spec,
            supports_check_mode=True
        )

        self.na_helper = NetAppModule()
        self.parameters = self.na_helper.set_parameters(self.module.params)
        self.rest_modify_zapi_to_rest = dict(
            # initiator_group_type (protocol) cannot be changed after create
            bind_portset='portset',
            name='name',
            os_type='os_type'
        )

        if self.module.params.get('initiators') is not None:
            self.parameters['initiators'] = [self.na_helper.sanitize_wwn(initiator)
                                             for initiator in self.module.params['initiators']]

        self.rest_api = OntapRestAPI(self.module)
        self.use_rest = self.rest_api.is_rest()

        def too_old_for_rest(minimum_generation, minimum_major):
            return self.use_rest and self.rest_api.get_ontap_version() < (minimum_generation, minimum_major)

        ontap_99_options = ['bind_portset']
        if too_old_for_rest(9, 9) and any(x in self.parameters for x in ontap_99_options):
            self.module.warn('Warning: falling back to ZAPI: %s' % self.rest_api.options_require_ontap_version(ontap_99_options, version='9.9'))
            self.use_rest = False

        if not self.use_rest:
            if HAS_NETAPP_LIB is False:
                self.module.fail_json(
                    msg="the python NetApp-Lib module is required")
            else:
                self.server = netapp_utils.setup_na_ontap_zapi(module=self.module, vserver=self.parameters['vserver'])

    def fail_on_error(self, error, stack=False):
        if error is None:
            return
        elements = dict(msg="Error: %s" % error)
        if stack:
            elements['stack'] = traceback.format_stack()
        self.module.fail_json(**elements)

    def get_igroup_rest(self, name):
        api = "protocols/san/igroups"
        query = dict(name=name, fields='name,uuid,svm,initiators,os_type,protocol')
        query['svm.name'] = self.parameters['vserver']
        response, error = self.rest_api.get(api, query)
        igroup, error = rrh.check_for_0_or_1_records(api, response, error)
        self.fail_on_error(error)
        if igroup:
            try:
                igroup_details = dict(
                    name=igroup['name'],
                    uuid=igroup['uuid'],
                    vserver=igroup['svm']['name'],
                    os_type=igroup['os_type'],
                    initiator_group_type=igroup['protocol'],
                )
            except KeyError as exc:
                self.module.fail_json(msg='Error: unexpected igroup body: %s, KeyError on %s' % (str(igroup), str(exc)))
            if 'initiators' in igroup:
                igroup_details['initiators'] = [item['name'] for item in igroup['initiators']]
            else:
                igroup_details['initiators'] = []
            return igroup_details
        return None

    def get_igroup(self, name):
        """
        Return details about the igroup
        :param:
            name : Name of the igroup

        :return: Details about the igroup. None if not found.
        :rtype: dict
        """
        if self.use_rest:
            return self.get_igroup_rest(name)

        igroup_info = netapp_utils.zapi.NaElement('igroup-get-iter')
        attributes = dict(query={'initiator-group-info': {'initiator-group-name': name,
                                                          'vserver': self.parameters['vserver']}})
        igroup_info.translate_struct(attributes)
        current = None

        try:
            result = self.server.invoke_successfully(igroup_info, True)
        except netapp_utils.zapi.NaApiError as error:
            self.module.fail_json(msg='Error fetching igroup info %s: %s' % (self.parameters['name'], to_native(error)),
                                  exception=traceback.format_exc())
        if result.get_child_by_name('num-records') and int(result.get_child_content('num-records')) >= 1:
            igroup_info = result.get_child_by_name('attributes-list')
            initiator_group_info = igroup_info.get_child_by_name('initiator-group-info')
            initiators = []
            if initiator_group_info.get_child_by_name('initiators'):
                current_initiators = initiator_group_info['initiators'].get_children()
                for initiator in current_initiators:
                    initiators.append(initiator['initiator-name'])
            current = {
                'initiators': initiators
            }
            zapi_to_params = {
                'vserver': 'vserver',
                'initiator-group-os-type': 'os_type',
                'initiator-group-portset-name': 'bind_portset',
                'initiator-group-type': 'initiator_group_type'
            }
            for attr in zapi_to_params:
                value = igroup_info.get_child_content(attr)
                if value is not None:
                    current[zapi_to_params[attr]] = value
        return current

    def add_initiators_rest(self, uuid, initiators):
        api = "protocols/san/igroups/%s/initiators" % uuid
        records = [dict(name=initiator) for initiator in initiators]
        body = dict(records=records)
        dummy, error = self.rest_api.post(api, body)
        self.fail_on_error(error)

    def add_initiators(self, uuid, current_initiators):
        """
        Add the list of desired initiators to igroup unless they are already set
        :return: None
        """
        # don't add if initiators is empty string
        if self.parameters.get('initiators') == [''] or self.parameters.get('initiators') is None:
            return
        initiators_to_add = [initiator for initiator in self.parameters['initiators'] if initiator not in current_initiators]
        if self.use_rest and uuid is not None and initiators_to_add:
            self.add_initiators_rest(uuid, initiators_to_add)
        else:
            for initiator in initiators_to_add:
                self.modify_initiator(initiator, 'igroup-add')

    def delete_initiator_rest(self, uuid, initiator):
        api = "protocols/san/igroups/%s/initiators/%s" % (uuid, initiator)
        dummy, error = self.rest_api.delete(api)
        self.fail_on_error(error)

    def remove_initiators(self, uuid, current_initiators):
        """
        Removes current initiators from igroup unless they are still desired
        :return: None
        """
        for initiator in current_initiators:
            if initiator not in self.parameters.get('initiators', list()):
                if self.use_rest:
                    self.delete_initiator_rest(uuid, initiator)
                else:
                    self.modify_initiator(initiator, 'igroup-remove')

    def modify_initiator(self, initiator, zapi):
        """
        Add or remove an initiator to/from an igroup
        """
        options = {'initiator-group-name': self.parameters['name'],
                   'initiator': initiator}

        igroup_modify = netapp_utils.zapi.NaElement.create_node_with_children(zapi, **options)

        try:
            self.server.invoke_successfully(igroup_modify, enable_tunneling=True)
        except netapp_utils.zapi.NaApiError as error:
            self.module.fail_json(msg='Error modifying igroup initiator %s: %s' % (self.parameters['name'],
                                                                                   to_native(error)),
                                  exception=traceback.format_exc())

    def create_igroup_rest(self):
        api = "protocols/san/igroups"
        body = dict(
            name=self.parameters['name'],
            os_type=self.parameters['os_type'])
        body['svm'] = dict(name=self.parameters['vserver'])
        mapping = dict(
            initiator_group_type='protocol',
            bind_portset='portset',
            initiators='initiators'
        )
        for option in mapping:
            value = self.parameters.get(option)
            if value is not None:
                if option == 'initiators':
                    value = [dict(name=initiator) for initiator in value]
                body[mapping[option]] = value
        dummy, error = self.rest_api.post(api, body)
        self.fail_on_error(error)

    def create_igroup(self):
        """
        Create the igroup.
        """
        if self.use_rest:
            self.create_igroup_rest()
            return

        options = {'initiator-group-name': self.parameters['name']}
        if self.parameters.get('os_type') is not None:
            options['os-type'] = self.parameters['os_type']
        if self.parameters.get('initiator_group_type') is not None:
            options['initiator-group-type'] = self.parameters['initiator_group_type']
        if self.parameters.get('bind_portset') is not None:
            options['bind-portset'] = self.parameters['bind_portset']

        igroup_create = netapp_utils.zapi.NaElement.create_node_with_children(
            'igroup-create', **options)

        try:
            self.server.invoke_successfully(igroup_create,
                                            enable_tunneling=True)
        except netapp_utils.zapi.NaApiError as error:
            self.module.fail_json(msg='Error provisioning igroup %s: %s' % (self.parameters['name'], to_native(error)),
                                  exception=traceback.format_exc())
        self.add_initiators(None, [])

    def modify_igroup_rest(self, uuid, modify):
        api = "protocols/san/igroups/%s" % uuid
        body = dict()
        for option in modify:
            if option not in self.rest_modify_zapi_to_rest:
                self.module.fail_json(msg='Error: modifying %s is not supported in REST' % option)
            body[self.rest_modify_zapi_to_rest[option]] = modify[option]
        if body:
            dummy, error = self.rest_api.patch(api, body)
            self.fail_on_error(error)

    def delete_igroup_rest(self, uuid):
        api = "protocols/san/igroups/%s" % uuid
        if self.parameters['force_remove_initiator']:
            query = dict(allow_delete_while_mapped=True)
        else:
            query = None
        dummy, error = self.rest_api.delete(api, params=query)
        self.fail_on_error(error)

    def delete_igroup(self, uuid):
        """
        Delete the igroup.
        """
        if self.use_rest:
            self.delete_igroup_rest(uuid)
            return

        igroup_delete = netapp_utils.zapi.NaElement.create_node_with_children(
            'igroup-destroy', **{'initiator-group-name': self.parameters['name'],
                                 'force': 'true' if self.parameters['force_remove_initiator'] else 'false'})

        try:
            self.server.invoke_successfully(igroup_delete,
                                            enable_tunneling=True)
        except netapp_utils.zapi.NaApiError as error:
            self.module.fail_json(msg='Error deleting igroup %s: %s' % (self.parameters['name'], to_native(error)),
                                  exception=traceback.format_exc())

    def rename_igroup(self):
        """
        Rename the igroup.
        """
        if self.use_rest:
            self.module.fail_json('Internal error, should not call rename, but use modify')

        igroup_rename = netapp_utils.zapi.NaElement.create_node_with_children(
            'igroup-rename', **{'initiator-group-name': self.parameters['from_name'],
                                'initiator-group-new-name': str(self.parameters['name'])})
        try:
            self.server.invoke_successfully(igroup_rename,
                                            enable_tunneling=True)
        except netapp_utils.zapi.NaApiError as error:
            self.module.fail_json(msg='Error renaming igroup %s: %s' % (self.parameters['name'], to_native(error)),
                                  exception=traceback.format_exc())

    def report_error_in_modify(self, modify, context):
        if modify:
            if len(modify) > 1:
                tag = 'any of '
            else:
                tag = ''
            self.module.fail_json(msg='Error: modifying %s %s is not supported in %s' % (tag, str(modify), context))

    def validate_modify(self, modify):
        """Identify options that cannot be modified for REST or ZAPI
        """
        if not modify:
            return
        modify_local = dict(modify)
        modify_local.pop('initiators', None)
        if not self.use_rest:
            self.report_error_in_modify(modify_local, 'ZAPI')
            return
        for option in modify:
            if option in self.rest_modify_zapi_to_rest:
                modify_local.pop(option)
        self.report_error_in_modify(modify_local, 'REST')

    def autosupport_log(self):
        if not self.use_rest:
            netapp_utils.ems_log_event("na_ontap_igroup", self.server)

    def is_rename_action(self, cd_action, current):
        old = self.get_igroup(self.parameters['from_name'])
        rename = self.na_helper.is_rename_action(old, current)
        if rename is None:
            self.module.fail_json(msg='Error: igroup with from_name=%s not found' % self.parameters.get('from_name'))
        if rename:
            current = old
            cd_action = None
        return cd_action, rename, current

    def apply(self):
        self.autosupport_log()
        uuid = None
        rename, modify = None, None
        current = self.get_igroup(self.parameters['name'])
        cd_action = self.na_helper.get_cd_action(current, self.parameters)
        if cd_action == 'create' and self.parameters.get('from_name'):
            cd_action, rename, current = self.is_rename_action(cd_action, current)
        if cd_action is None and self.parameters['state'] == 'present':
            modify = self.na_helper.get_modified_attributes(current, self.parameters)
            # a change in name is handled in rename for ZAPI, but REST can use modify
            if self.use_rest:
                rename = False
            else:
                modify.pop('name', None)
        if current and self.use_rest:
            uuid = current['uuid']
        if cd_action == 'create' and self.use_rest and 'os_type' not in self.parameters:
            self.module.fail_json(msg='Error: os_type is a required parameter when creating an igroup with REST')
        self.validate_modify(modify)

        if self.na_helper.changed and not self.module.check_mode:
            if rename:
                self.rename_igroup()
            elif cd_action == 'create':
                self.create_igroup()
            elif cd_action == 'delete':
                self.delete_igroup(uuid)
            if modify:
                self.remove_initiators(uuid, current['initiators'])
                self.add_initiators(uuid, current['initiators'])
                modify.pop('initiators', None)
                if modify:
                    self.modify_igroup_rest(uuid, modify)
        self.module.exit_json(changed=self.na_helper.changed, current=current, modify=modify)


def main():
    obj = NetAppOntapIgroup()
    obj.apply()


if __name__ == '__main__':
    main()
