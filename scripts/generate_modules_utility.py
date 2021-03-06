from jinja2 import Template, Environment, FileSystemLoader
import json
import os


def generate_cofiguration_fact_rst(schema_results, version):
    file_loader = FileSystemLoader('ansible_templates')
    env = Environment(loader=file_loader,
                      lstrip_blocks=False, trim_blocks=False)
    template = env.get_template('configuration_fact.rst.j2')

    selectors = dict()
    for schema_result in schema_results:
        selector = schema_result['path'] + "_" + schema_result['name']
        mkey = schema_result['schema'].get('mkey', None)
        mkey_type = schema_result['schema'].get('mkey_type', None)
        if mkey_type == 'integer':
            mkey_type = 'int'
        elif mkey_type:
            mkey_type = 'str'
        else:
            assert(mkey_type == None)
        selectors[selector] =dict()
        selectors[selector]['mkey'] = mkey
        selectors[selector]['mkey_type'] = mkey_type
    data = template.render(selectors=selectors)

    output_path = 'output/' + version + '/fortios_configuration_fact.rst'
    with open(output_path, 'w') as f:
        f.write(data)
        f.flush()


def generate_monitor_fact(version):
    monitor_schema_file = open('monitor_schema.json').read()
    monitor_schema = json.loads(monitor_schema_file)
    get_api_items = dict()
    assert('directory' in monitor_schema)
    for api_item in monitor_schema['directory']:
        assert('request' in api_item)
        assert('http_method' in api_item['request'])
        if api_item['request']['http_method'] != 'GET':
            continue
        path = api_item['path']
        name = api_item['name']
        action = api_item['action']
        key = '%s/%s' % (path, name)
        if action != 'select':
            key = '%s/%s' % (key, action)
        assert(key not in get_api_items)
        get_api_items[key] = api_item
    schemas = dict()
    for api_item_key in get_api_items:
        api_item = get_api_items[api_item_key]
        selector = api_item_key.replace('/', '_')
        assert(selector not in schemas)
        schemas[selector] = dict()
        schemas[selector]['url'] = api_item_key
        schemas[selector]['params'] = dict()
        assert(api_item['request']['http_method'] == 'GET')
        if 'parameters' in api_item['request']:
            for param in api_item['request']['parameters']:
                param_name = param['name']
                param_type = param['type']
                param_required = True if 'required' in param and param['required'] else False
                param_desc = param['summary'] if 'summary' in param else ''
                schemas[selector]['params'][param_name] = dict()
                schemas[selector]['params'][param_name]['type'] = param_type
                schemas[selector]['params'][param_name]['description'] = param_desc
                schemas[selector]['params'][param_name]['required'] = param_required
                schemas[selector]['description'] = api_item['summary'] if 'summary' in api_item else ''
    file_loader = FileSystemLoader('ansible_templates')
    env = Environment(loader=file_loader,
                      lstrip_blocks=False, trim_blocks=False)

    # Render module code
    template = env.get_template('monitor_fact.j2')
    data = template.render(selectors=schemas)
    output_path = 'output/' + version + '/fortios_monitor_fact.py'
    with open(output_path, 'w') as f:
        f.write(data)
        f.flush()
    # Render Sphinx doc
    template = env.get_template('monitor_fact.rst.j2')
    data = template.render(selectors=schemas)
    output_path = 'output/' + version + '/fortios_monitor_fact.rst'
    with open(output_path, 'w') as f:
        f.write(data)
        f.flush()


def generate_monitor_modules(version):
    # Init template to generate a single module
    file_loader = FileSystemLoader('ansible_templates')
    env = Environment(loader=file_loader,
                      lstrip_blocks=False, trim_blocks=False)
    template = env.get_template('monitor_config.j2')

    monitor_schema_file = open('monitor_schema.json').read()
    monitor_schema = json.loads(monitor_schema_file)
    post_api_items = dict()
    assert('directory' in monitor_schema)
    for api_item in monitor_schema['directory']:
        assert('request' in api_item)
        assert('http_method' in api_item['request'])
        if api_item['request']['http_method'] != 'POST':
            continue
        path = api_item['path']
        name = api_item['name']
        action = api_item['action']
        key = '%s/%s/%s' % (path, name, action)
        assert(key not in post_api_items)
        post_api_items[key] = api_item
    schemas = dict()
    for api_item_key in post_api_items:
        api_item = post_api_items[api_item_key]
        selector = '%s.%s.%s' % (api_item['action'], api_item['path'], api_item['name'])
        if api_item['action'] == 'select':
            selector = '%s.%s' % (api_item['path'], api_item['name'])
        assert(selector not in schemas)
        schemas[selector] = dict()
        schemas[selector]['url'] = api_item_key
        schemas[selector]['params'] = dict()
        assert(api_item['request']['http_method'] == 'POST')
        if 'parameters' in api_item['request']:
            for param in api_item['request']['parameters']:
                param_name = param['name']
                param_type = param['type']
                param_required = True if 'required' in param and param['required'] else False
                param_desc = param['summary'] if 'summary' in param else ''
                schemas[selector]['params'][param_name] = dict()
                schemas[selector]['params'][param_name]['type'] = param_type
                schemas[selector]['params'][param_name]['description'] = param_desc
                schemas[selector]['params'][param_name]['required'] = param_required
                schemas[selector]['description'] = api_item['summary'] if 'summary' in api_item else ''

    data = template.render(selectors=schemas)
    output_path = 'output/' + version + '/fortios_monitor.py'
    with open(output_path, 'w') as f:
        f.write(data)
        f.flush()


def generate_monitor_rst(version):
    file_loader = FileSystemLoader('ansible_templates')
    env = Environment(loader=file_loader,
                      lstrip_blocks=False, trim_blocks=False)
    monitor_schema_file = open('monitor_schema.json').read()
    monitor_schema = json.loads(monitor_schema_file)
    post_api_items = dict()
    assert('directory' in monitor_schema)
    for api_item in monitor_schema['directory']:
        assert('request' in api_item)
        assert('http_method' in api_item['request'])
        if api_item['request']['http_method'] != 'POST':
            continue
        path = api_item['path']
        name = api_item['name']
        action = api_item['action']
        key = '%s.%s.%s' % (action, path, name)
        if action == 'select':
            key = '%s.%s' % (path, name)
        assert(key not in post_api_items)
        post_api_items[key] = api_item
    schemas = dict()
    for api_item_key in post_api_items:
        api_item = post_api_items[api_item_key]
        schemas[api_item_key] = dict()
        schemas[api_item_key]['description'] = api_item['summary'] if 'summary' in api_item else ''
        schemas[api_item_key]['params'] = dict()
        if 'parameters' in api_item['request']:
            for param in api_item['request']['parameters']:
                param_name = param['name']
                param_type = param['type']
                param_required = True if 'required' in param and param['required'] else False
                param_desc = param['summary']
                schemas[api_item_key]['params'][param_name] = dict()
                schemas[api_item_key]['params'][param_name]['type'] = param_type
                schemas[api_item_key]['params'][param_name]['required'] = param_required
                schemas[api_item_key]['params'][param_name]['description'] = param_desc
    template = env.get_template('monitor.rst.j2')
    data = template.render(actions=schemas)
    output_path = 'output/' + version + '/fortios_monitor.rst'
    with open(output_path, 'w') as f:
        f.write(data)
        f.flush()


def generate_log_fact(version):
    log_schema_file = open('log_schema.json').read()
    log_schema = json.loads(log_schema_file)
    get_api_items = dict()
    assert('directory' in log_schema)
    for api_item in log_schema['directory']:
        assert('request' in api_item)
        assert('http_method' in api_item['request'])
        if api_item['request']['http_method'] != 'GET':
            continue

        for path in ['disk', 'memory', 'fortianalyzer', 'forticloud']:
            name = api_item['name']
            action = api_item['action']
            if name == 'virus':
                names = [name]
            elif name == ':type' and action in ['archive', 'archive-download']:
                names = ['ips', 'app-ctrl']
            elif name == ':type' and action == 'raw':
                names = ['virus', 'webfilter', 'waf', 'ips', 'anomaly', 'app-ctrl', 'cifs',
                    'emailfilter', 'dlp', 'voip', 'gtp', 'dns', 'ssh', 'ssl', 'file-filter']
            else:
                names = ['event', 'traffic']
            for actual_name in names:
                actions = [action]
                if action == '?subtype':
                    if actual_name == 'event':
                        actions = ['vpn', 'user', 'router', 'wireless',
                        'wad', 'endpoint', 'ha', 'compliance-check', 'system',
                        'connector', 'security-rating', 'fortiextender']
                    else:
                        actions = ['forward', 'local', 'multicast', 'sniffer',
                        'fortiview', 'threat']
                for actual_action in actions:
                    key = '%s/%s/%s' % (path, actual_name, actual_action)
                    assert(key not in get_api_items)
                    get_api_items[key] = api_item
    schemas = dict()
    for api_item_key in get_api_items:
        api_item = get_api_items[api_item_key]
        selector = api_item_key.replace('/', '_')
        assert(selector not in schemas)
        schemas[selector] = dict()
        schemas[selector]['url'] = api_item_key
        schemas[selector]['params'] = dict()
        assert(api_item['request']['http_method'] == 'GET')
        if 'parameters' in api_item['request']:
            for param in api_item['request']['parameters']:
                param_name = param['name']
                param_type = param['type']
                param_desc = param['summary'] if 'summary' in param else ''
                schemas[selector]['params'][param_name] = dict()
                schemas[selector]['params'][param_name]['type'] = param_type
                schemas[selector]['params'][param_name]['description'] = param_desc
                schemas[selector]['description'] = api_item['summary'] if 'summary' in api_item else ''
    file_loader = FileSystemLoader('ansible_templates')
    env = Environment(loader=file_loader,
                      lstrip_blocks=False, trim_blocks=False)

    # Render module code
    template = env.get_template('log_fact.j2')
    data = template.render(selectors=schemas)
    output_path = 'output/' + version + '/fortios_log_fact.py'
    with open(output_path, 'w') as f:
        f.write(data)
        f.flush()
    # Render Sphinx doc
    template = env.get_template('log_fact.rst.j2')
    data = template.render(selectors=schemas)
    output_path = 'output/' + version + '/fortios_log_fact.rst'
    with open(output_path, 'w') as f:
        f.write(data)
        f.flush()


if __name__ == '__main__':
    generate_cofiguration_fact_rst()
    generate_monitor_fact('v6.0.0')
    generate_monitor_modules('v6.0.0')
