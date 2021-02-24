# This code is part of Ansible, but is an independent component.
# This particular file snippet, and this file snippet only, is BSD licensed.
# Modules you write using this snippet, which is embedded dynamically by Ansible
# still belong to the author of the module, and may assign their own license
# to the complete work.
#
# Miguel Angel Munoz <magonzalez@fortinet.com>, 2019
# fortinet-ansible-dev <https://github.com/fortinet-ansible-dev>, 2020
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE
#

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import time
import traceback

from ansible.module_utils._text import to_text
from ansible.module_utils.basic import env_fallback
from ansible.module_utils.basic import _load_params
import sys
import json

try:
    import urllib.parse as urlencoding
except ImportError:
    import urllib as urlencoding

# BEGIN DEPRECATED

# check for pyFG lib
try:
    from pyFG import FortiOS, FortiConfig
    from pyFG.exceptions import FailedCommit
    HAS_PYFG = True
except ImportError:
    HAS_PYFG = False

fortios_required_if = [
    ['file_mode', False, ['host', 'username', 'password']],
    ['file_mode', True, ['config_file']],
    ['backup', True, ['backup_path']],
]

fortios_mutually_exclusive = [
    ['config_file', 'host'],
    ['config_file', 'username'],
    ['config_file', 'password']
]

fortios_error_codes = {
    '-3': "Object not found",
    '-61': "Command error"
}


def check_legacy_fortiosapi():
    params = _load_params()
    legacy_schemas = ['host', 'username', 'password', 'ssl_verify', 'https']
    legacy_params = []
    for param in legacy_schemas:
        if param in params:
            legacy_params.append(param)
    if len(legacy_params):
        error_message = 'Legacy fortiosapi parameters %s detected, please use HTTPAPI instead!' % (str(legacy_params))
        sys.stderr.write(error_message)
        sys.exit(1)


def schema_to_module_spec(schema):
    rdata = dict()
    assert('type' in schema)
    if schema['type'] == 'dict' or (schema['type'] == 'list' and 'children' in schema):
        assert('children' in schema)
        rdata['type'] = schema['type']
        rdata['required'] = False
        rdata['options'] = dict()
        for child in schema['children']:
            child_value = schema['children'][child]
            rdata['options'][child] = schema_to_module_spec(child_value)
    elif schema['type'] in ['integer', 'string'] or (schema['type'] == 'list' and 'children' not in schema):
        if schema['type'] == 'integer':
            rdata['type'] = 'int'
        elif schema['type'] == 'string':
            rdata['type'] = 'str'
        elif schema['type'] == 'list':
            rdata['type'] = 'list'
        else:
            assert(False)
        rdata['required'] = False
        if 'options' in schema:
            # see mantis #0690570, if the semantic meaning changes, remove choices as well
            # also see accept_auth_by_cert of module fortios_system_csf.
            param_semantic_changed = False
            for ver in schema['revisions']:
                if not schema['revisions']:
                    continue
                for option in schema['options']:
                    if ver not in option['revisions']:
                        param_semantic_changed = True
                        break
                if param_semantic_changed:
                    break
            if not param_semantic_changed:
                rdata['choices'] = [option['value'] for option in schema['options']]
    else:
        assert(False)
    return rdata

def __check_version(revisions, version):
    result = dict()
    resolved_versions = list(revisions.keys())
    resolved_versions.sort(key=lambda x: int(x.split('.')[0][1]) * 10000 + int(x.split('.')[1]) * 100 + int(x.split('.')[2]))
    # try to detect the versioning gaps and mark them as violations:
    nearest_index = -1
    for i in range(len(resolved_versions)):
        if resolved_versions[i] <= version:
            nearest_index = i
    if nearest_index == -1:
        # even it's not supported in earliest version
        result['supported'] = False
        result['reason'] = 'not supported until in %s' % (resolved_versions[0])
    else:
        if revisions[resolved_versions[nearest_index]] is False:
            latest_index = -1
            for i in range(nearest_index + 1, len(resolved_versions)):
                if revisions[resolved_versions[i]] is True:
                    latest_index = i
                    break
            earliest_index = nearest_index
            while earliest_index >= 0:
                if revisions[resolved_versions[earliest_index]] is True:
                    break
                earliest_index -= 1
            earliest_index = 0 if earliest_index < 0 else earliest_index
            if latest_index == -1:
                result['reason'] = 'not supported since %s' % (resolved_versions[earliest_index])
            else:
                result['reason'] = 'not supported since %s, before %s' % (resolved_versions[earliest_index], resolved_versions[latest_index])
            result['supported'] = False
        else:
            result['supported'] = True
    return result


def __concat_attribute_sequence(trace_path):
    rdata = ''
    assert(type(trace_path) is list)
    if len(trace_path) >= 1:
        rdata += str(trace_path[0])
    for item in trace_path[1:]:
        rdata += '.' + str(item)
    return rdata


def check_schema_versioning_internal(results, trace, schema, params, version):
    if not schema or not params:
        return
    assert('revisions' in schema)
    revision = schema['revisions']
    matched = __check_version(revision, version)
    if matched['supported'] is False:
        results['mismatches'].append('option %s %s' % (__concat_attribute_sequence(trace), matched['reason']))

    if 'type' not in schema:
        return

    if schema['type'] == 'list':
        assert(type(params) is list)
        if 'children' in schema:
            assert('options' not in schema)
            for list_item in params:
                assert(type(list_item) is dict)
                for key in list_item:
                    value = list_item[key]
                    key_string = '%s(%s)' %(key, value) if type(value) in [int, bool, str] else key
                    trace.append(key_string)
                    check_schema_versioning_internal(results, trace, schema['children'][key], value, version)
                    del trace[-1]
        else:
            assert('options' in schema)
            for param in params:
                assert(type(param) in [int, bool, str])
                target_option = None
                for option in schema['options']:
                    if option['value'] == param:
                        target_option = option
                        break
                assert(target_option)
                trace.append('[%s]' % param)
                check_schema_versioning_internal(results, trace, target_option, param, version)
                del trace[-1]
    elif schema['type'] == 'dict':
        assert(type(params) is dict)
        if 'children' in schema:
            for dict_item_key in params:
                dict_item_value = params[dict_item_key]
                assert(dict_item_key in schema['children'])
                key_string = '%s(%s)' %(dict_item_key, dict_item_value) if type(dict_item_value) in [int, bool, str] else dict_item_key
                trace.append(key_string)
                check_schema_versioning_internal(results, trace, schema['children'][dict_item_key], dict_item_value, version)
                del trace[-1]
    else:
        assert(type(params) in [int, str, bool])

def check_schema_versioning(fos, versioned_schema, top_level_param):
    trace = list()
    results = dict()
    results['matched'] = True
    results['mismatches'] = list()

    system_version = fos._conn.get_system_version()
    params = fos._module.params[top_level_param]
    results['system_version'] = system_version
    if not params:
        # in case no top level parameters are given.
        # see module: fortios_firewall_policy
        return results
    module_revisions = versioned_schema['revisions']
    module_matched = __check_version(module_revisions, system_version)
    if module_matched['supported'] is False:
        results['matched'] = False
        results['mismatches'].append('module fortios_%s %s' % (top_level_param, module_matched['reason']))
        return results

    for param_name in params:
        param_value = params[param_name]
        if not param_value or param_name not in versioned_schema['children']:
            continue
        key_string = '%s(%s)' %(param_name, param_value) if type(param_value) in [int, bool, str] else param_name
        trace.append(key_string)
        check_schema_versioning_internal(results, trace, versioned_schema['children'][param_name], param_value, system_version)
        del trace[-1]
    if len(results['mismatches']):
        results['matched'] = False

    return results


# END DEPRECATED


class FortiOSHandler(object):

    def __init__(self, conn, mod, module_mkeyname=None):
        self._conn = conn
        self._module = mod
        self._mkeyname = module_mkeyname

    def cmdb_url(self, path, name, vdom=None, mkey=None):

        url = '/api/v2/cmdb/' + path + '/' + name
        if mkey:
            url = url + '/' + urlencoding.quote(str(mkey), safe='')
        if vdom:
            if vdom == "global":
                url += '?global=1'
            else:
                url += '?vdom=' + vdom
        return url

    def mon_url(self, path, name, vdom=None, mkey=None):
        url = '/api/v2/monitor/' + path + '/' + name
        if mkey:
            url = url + '/' + urlencoding.quote(str(mkey), safe='')
        if vdom:
            if vdom == "global":
                url += '?global=1'
            else:
                url += '?vdom=' + vdom
        return url

    def schema(self, path, name, vdom=None):
        if vdom is None:
            url = self.cmdb_url(path, name) + "?action=schema"
        else:
            url = self.cmdb_url(path, name, vdom=vdom) + "&action=schema"

        status, result_data = self._conn.send_request(url=url)

        if status == 200:
            if vdom == "global":
                return json.loads(to_text(result_data))[0]['results']
            else:
                return json.loads(to_text(result_data))['results']
        else:
            return json.loads(to_text(result_data))

    def get_mkeyname(self, path, name, vdom=None):
        return self._mkeyname

    def get_mkey(self, path, name, data, vdom=None):

        keyname = self.get_mkeyname(path, name, vdom)
        if not keyname:
            return None
        else:
            try:
                mkey = data[keyname]
            except KeyError:
                return None
        return mkey

    def monitor_get(self, url, vdom=None, parameters=None):
        slash_index = url.find('/')
        full_url = self.mon_url(url[: slash_index], url[slash_index + 1: ], vdom)
        status, result_data = self._conn.send_request(url=full_url, params=parameters, method='GET')
        return self.formatresponse(result_data, vdom=vdom)

    def get(self, path, name, vdom=None, mkey=None, parameters=None):
        url = self.cmdb_url(path, name, vdom, mkey=mkey)

        status, result_data = self._conn.send_request(url=url, params=parameters, method='GET')

        return self.formatresponse(result_data, vdom=vdom)

    def monitor(self, path, name, vdom=None, mkey=None, parameters=None):
        url = self.mon_url(path, name, vdom, mkey)

        status, result_data = self._conn.send_request(url=url, params=parameters, method='GET')

        return self.formatresponse(result_data, vdom=vdom)

    def set(self, path, name, data, mkey=None, vdom=None, parameters=None):

        if not mkey:
            mkey = self.get_mkey(path, name, data, vdom=vdom)
        url = self.cmdb_url(path, name, vdom, mkey)

        status, result_data = self._conn.send_request(url=url, params=parameters, data=json.dumps(data), method='PUT')

        if parameters and 'action' in parameters and parameters['action'] == 'move':
            return self.formatresponse(result_data, vdom=vdom)

        if status == 404 or status == 405 or status == 500:
            return self.post(path, name, data, vdom, mkey)
        else:
            return self.formatresponse(result_data, vdom=vdom)

    def post(self, path, name, data, vdom=None,
             mkey=None, parameters=None):

        if mkey:
            mkeyname = self.get_mkeyname(path, name, vdom)
            data[mkeyname] = mkey

        url = self.cmdb_url(path, name, vdom, mkey=None)

        status, result_data = self._conn.send_request(url=url, params=parameters, data=json.dumps(data), method='POST')

        return self.formatresponse(result_data, vdom=vdom)

    def execute(self, path, name, data, vdom=None,
                mkey=None, parameters=None, timeout=300):
        url = self.mon_url(path, name, vdom, mkey=mkey)

        status, result_data = self._conn.send_request(url=url, params=parameters, data=json.dumps(data), method='POST', timeout=timeout)

        return self.formatresponse(result_data, vdom=vdom)

    def delete(self, path, name, vdom=None, mkey=None, parameters=None, data=None):
        if not mkey:
            mkey = self.get_mkey(path, name, data, vdom=vdom)
        url = self.cmdb_url(path, name, vdom, mkey)
        status, result_data = self._conn.send_request(url=url, params=parameters, data=json.dumps(data), method='DELETE')
        return self.formatresponse(result_data, vdom=vdom)

    def __to_local(self, data, is_array=False):
        try:
            resp = json.loads(data)
        except:
            resp = {'raw': data}
        if is_array and type(resp) is not list:
            resp = [resp]
        if is_array and 'status' not in resp[0]:
            resp[0]['status'] = 'success'
        elif not is_array and 'status' not in resp:
            resp['status'] = 'success'
        return resp

    def formatresponse(self, res, vdom=None):
        if vdom == "global":
            resp = self.__to_local(to_text(res), True)[0]
            resp['vdom'] = "global"
        else:
            resp = self.__to_local(to_text(res), False)
        return resp

    def jsonraw(self, method, path, data, specific_params, vdom=None, parameters=None):
        url = path
        bvdom = False
        if vdom:
            if vdom == "global":
                url += '?global=1'
            else:
                url += '?vdom=' + vdom
            bvdom = True
        if specific_params:
            if bvdom:
                url += '&'
            else:
                url += "?"
            url += specific_params
        status, result_data = self._conn.send_request(url=url, method=method, data=json.dumps(data), params=parameters)
        return self.formatresponse(result_data, vdom=vdom)

# BEGIN DEPRECATED


def backup(module, running_config):
    backup_path = module.params['backup_path']
    backup_filename = module.params['backup_filename']
    if not os.path.exists(backup_path):
        try:
            os.mkdir(backup_path)
        except Exception:
            module.fail_json(msg="Can't create directory {0} Permission denied ?".format(backup_path))
    tstamp = time.strftime("%Y-%m-%d@%H:%M:%S", time.localtime(time.time()))
    if 0 < len(backup_filename):
        filename = '%s/%s' % (backup_path, backup_filename)
    else:
        filename = '%s/%s_config.%s' % (backup_path, module.params['host'], tstamp)
    try:
        open(filename, 'w').write(running_config)
    except Exception:
        module.fail_json(msg="Can't create backup file {0} Permission denied ?".format(filename))


class AnsibleFortios(object):
    def __init__(self, module):
        if not HAS_PYFG:
            module.fail_json(msg='Could not import the python library pyFG required by this module')

        self.result = {
            'changed': False,
        }
        self.module = module

    def _connect(self):
        if self.module.params['file_mode']:
            self.forti_device = FortiOS('')
        else:
            host = self.module.params['host']
            username = self.module.params['username']
            password = self.module.params['password']
            timeout = self.module.params['timeout']
            vdom = self.module.params['vdom']

            self.forti_device = FortiOS(host, username=username, password=password, timeout=timeout, vdom=vdom)

            try:
                self.forti_device.open()
            except Exception as e:
                self.module.fail_json(msg='Error connecting device. %s' % to_text(e),
                                      exception=traceback.format_exc())

    def load_config(self, path):
        self.path = path
        self._connect()
        # load in file_mode
        if self.module.params['file_mode']:
            try:
                f = open(self.module.params['config_file'], 'r')
                running = f.read()
                f.close()
            except IOError as e:
                self.module.fail_json(msg='Error reading configuration file. %s' % to_text(e),
                                      exception=traceback.format_exc())
            self.forti_device.load_config(config_text=running, path=path)

        else:
            # get  config
            try:
                self.forti_device.load_config(path=path)
            except Exception as e:
                self.forti_device.close()
                self.module.fail_json(msg='Error reading running config. %s' % to_text(e),
                                      exception=traceback.format_exc())

        # set configs in object
        self.result['running_config'] = self.forti_device.running_config.to_text()
        self.candidate_config = self.forti_device.candidate_config

        # backup if needed
        if self.module.params['backup']:
            backup(self.module, self.forti_device.running_config.to_text())

    def apply_changes(self):
        change_string = self.forti_device.compare_config()
        if change_string:
            self.result['change_string'] = change_string
            self.result['changed'] = True

        # Commit if not check mode
        if change_string and not self.module.check_mode:
            if self.module.params['file_mode']:
                try:
                    f = open(self.module.params['config_file'], 'w')
                    f.write(self.candidate_config.to_text())
                    f.close()
                except IOError as e:
                    self.module.fail_json(msg='Error writing configuration file. %s' %
                                          to_text(e), exception=traceback.format_exc())
            else:
                try:
                    self.forti_device.commit()
                except FailedCommit as e:
                    # Something's wrong (rollback is automatic)
                    self.forti_device.close()
                    error_list = self.get_error_infos(e)
                    self.module.fail_json(msg_error_list=error_list, msg="Unable to commit change, check your args, the error was %s" % e.message)

                self.forti_device.close()
        self.module.exit_json(**self.result)

    def del_block(self, block_id):
        self.forti_device.candidate_config[self.path].del_block(block_id)

    def add_block(self, block_id, block):
        self.forti_device.candidate_config[self.path][block_id] = block

    def get_error_infos(self, cli_errors):
        error_list = []
        for errors in cli_errors.args:
            for error in errors:
                error_code = error[0]
                error_string = error[1]
                error_type = fortios_error_codes.get(error_code, "unknown")
                error_list.append(dict(error_code=error_code, error_type=error_type, error_string=error_string))

        return error_list

    def get_empty_configuration_block(self, block_name, block_type):
        return FortiConfig(block_name, block_type)

# END DEPRECATED

