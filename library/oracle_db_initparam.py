#!/usr/bin/env python

# Copyright 2016 Michitoshi Yoshida <miyosh0008@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

DOCUMENTATION = """
---
module: oracle_db_initparam
author: Michitoshi Yoshida (@miyosh0008)
short_description: Sets initialization parameters.
description:
    - Sets initialization parameters for Oracle databases.
requirements:
    - cx_Oracle
options:
    host:
        description:
            - Listener address (hostname/IP)
        required: true
    port:
        description:
            - Listener port (Typically 1521)
        required: true
    user:
        description:
            - Database username (Should use sys/system)
        required: true
    password:
        description:
            - Database user password
        required: true
    sid:
        description:
            - Database instance SID
        required: false
    service:
        description:
            - Database service name
        required: false
    as_sysdba:
        description:
            - Connect to database as SYSDBA (Should be true to set parameter settings)
        choices: [ True, False ]
        required: false
    name:
        description:
            - Name of the initialization parameter
        required: true
    value:
        description:
            - Value of the initialization parameter
        required: true
    scope:
        description:
            - Scope for setting the initialization parameter
        choices: [ None, 'MEMORY', 'SPFILE', 'BOTH' ]
        required: false
    instances:
        description:
            - Target instances for setting the initialization parameter (for RAC)
        required: false
"""

EXAMPLES = '''
# Set optimizer_use_invisible_indexes to FALSE (scope: BOTH)
- oracle_db_initparam:
    host=192.168.56.101 port=1521 sid=orcl
    user=sys password=welcome1 as_sysdba=True
    name=optimizer_use_invisible_indexes value=FALSE

# set sga_max_size to 8G (scope: SPFILE, instances: *)
- oracle_db_initparam:
    host=192.168.56.101 port=1521 service=racdb
    user=sys password=welcome1 as_sysdba=True
    name=sga_max_size value=16G scope=SPFILE instances=*
'''

try:
    import cx_Oracle
    has_cxOracle = True
except:
    has_cxOracle = False


def set_init_param(module,connection,name,value,scope=None,instances=None):
    cursor = connection.cursor()
    if scope == 'SPFILE':
        sql = u'select value,display_value \
        from v$spparameter where name = \'%s\'' % (name)
    else:
        sql = u'select value,display_value,issys_modifiable \
        from v$parameter where name = \'%s\'' % (name)

    resultset = []
    try:
        cursor.execute(sql)
        for row in cursor:
            resultset.append(row)
    except Exception, e:
        module.fail_json(msg='SQLException encountered (sql: %s, err: %s)' \
                             % (sql,str(e)))

    if len(resultset) == 0:
        module.fail_json(msg='Could not find init parameter (name: %s)' \
                             % (name))

    value_current = resultset[0][0]
    value_display_current = resultset[0][1]
    if scope != 'SPFILE':
        sys_modifiable = resultset[0][2]

    if value_current == value or value_display_current == value:
        return False
    else:
        if module.check_mode:
            return True

        if scope == 'SPFILE':
            sql = u'alter system set %s=%s scope=SPFILE' % (name,value)
        else:
            if sys_modifiable == 'IMMEDIATE':
                pass
            elif sys_modifiable == 'DEFERRED':
                pass
            else:
                module.fail_json(msg='Parameter cannot be changed online (name: %s)' \
                                     % (name))
            sql = u'alter system set %s=%s' % (name,value)

        if instances is not None:
            sql = sql + u' sid=\'%s\'' % (instances)

        try:
            cursor.execute(sql)
            return True
        except Exception, e:
            module.fail_json(msg='SQLException encountered (sql: %s, err: %s)' \
                             % (sql,str(e)))


def oracle_connect(module,host,port,user,password,
                   sid=None,service=None,as_sysdba=False):
    if sid is not None:
        dsn = cx_Oracle.makedsn(host,port,sid)
    elif service is not None:
        dsn = cx_Oracle.makedsn(host,port,service_name=service)

    try:
        if as_sysdba:
            conn = cx_Oracle.connect(user,password,dsn,
                                     mode=cx_Oracle.SYSDBA)
        else:
            conn = cx_Oracle.connect(user,password,dsn)
    except Exception, e:
        module.fail_json(msg='Cannot connect to database (err: %s)' % (str(e)))
    return conn


def main():
    module = AnsibleModule(
        argument_spec=dict(
            host=dict(required=True),
            port=dict(required=True, type='int'),
            user=dict(required=True),
            password=dict(required=True),
            sid=dict(required=False, default=None),
            service=dict(required=False, default=None),
            as_sysdba=dict(required=False, type='bool', default=False),
            name=dict(required=True),
            value=dict(required=True),
            scope=dict(required=False, default=None),
            instances=dict(required=False, default=None),
        ),
        mutually_exclusive=(['sid', 'service'],),
        required_one_of=(['sid', 'service'],),
        supports_check_mode=True
    )

    module_args = module.params

    if not has_cxOracle:
        module.fail_json(msg='cx_Oracle is missing.')

    if not module_args['scope']:
        module_args['scope'] = None

    if not module_args['instances']:
        module_args['instances'] = None

    has_changed = False
    conn = oracle_connect(
        module,
        host = module_args['host'],
        port = module_args['port'],
        user = module_args['user'],
        password = module_args['password'],
        sid = module_args['sid'],
        service = module_args['service'],
        as_sysdba = module_args['as_sysdba']
    )

    has_changed = set_init_param(
        module,
        conn,
        module_args['name'],
        module_args['value'],
        scope=module_args['scope'],
        instances=module_args['instances']
    )

    return_status = {'changed': has_changed}
    module.exit_json(**return_status)


from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
