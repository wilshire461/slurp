import sys
import urllib
import urllib2
import json
import datetime
import subprocess
import ast

import settings



# Max errors that can be encountered before slurp exits
ERROR_THRESHOLD = 10
err_cnt = 0

CLUSTER = 'cluster={}'.format(settings.CLUSTER_NAME)
FORMAT = 'format=account,user,maxjobs,qos,{}'.format(settings.AMOUNT_ATTRIBUTE)
AMOUNT = settings.AMOUNT_ATTRIBUTE

# Top Levels
TOP_LEVELS = [
    'condo',
    'ucb',
    'ucballoc',
    'rmacc',
    'rmaccalloc',
    'csu',
    'csualloc',
]

# General accounts
GENERAL_ACCOUNTS = [
    'ucball',
    'rmaccall',
    'csuall',
]

def exit_with_msg(err_msg):
    err_msg_ts = '{}: {}\n'.format(datetime.datetime.now(),err_msg)
    sys.stderr.write(err_msg_ts)
    sys.exit(1)

def log_error(err_msg):
    global err_cnt
    err_cnt += 1
    err_msg_ts = '{}: {}\n'.format(datetime.datetime.now(),err_msg)
    sys.stderr.write(err_msg_ts)
    if err_cnt > ERROR_THRESHOLD:
        emsg = "Too many failures encountered, exiting...\n"
        exit_with_msg(emsg)

def run_slurm_cmd(cmd, exit_on_failure=False):
    try:
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = p.communicate()
        if stderr != '':
            raise subprocess.CalledProcessError(
                p.returncode,
                subprocess.list2cmdline(cmd),
                stderr
            )
        return stdout

    except OSError:
        err_msg = "Slurm not found! Exiting...\n"
        exit_with_msg(err_msg)

    except subprocess.CalledProcessError as e:
        err_msg = 'Command error: {}\n{}\n'.format(e.cmd,e.output)
        if exit_on_failure:
            exit_with_msg(err_msg)
        log_error(err_msg)
        return None

def get_top_level(alloc):
    # Return the appropriate top-level given an allocation

    # Parent has been explicitly specified
    if 'parent' in alloc:
        return alloc['project']['parent']
    # Automatically determine from allocation_id
    if alloc['project']['project_id'].startswith('ucb'):
        return 'ucballoc'
    if alloc['project']['project_id'].startswith('rmacc'):
        return 'rmaccalloc'
    if alloc['project']['project_id'].startswith('csu'):
        return 'csualloc'

# Get Slurm State
cmd = [
    'sacctmgr',
    'show',
    'ass',
    FORMAT,
    CLUSTER,
    '-n',
    '-P',
]
output = run_slurm_cmd(cmd, exit_on_failure=True)

lines = output.split()
parsed = []
for line in lines:
    parsed.append(line.split('|'))

slurm_state = {}
for e in parsed:
    # Is an account, not a user
    if e[1] == '':
        d = {
            'users': [],
            'maxjobs': e[2],
            'qos': e[3],
            AMOUNT: e[4],
        }
        slurm_state[e[0]] = d
    else:
        if e[0] in slurm_state:
            slurm_state[e[0]]['users'].append(e[1])

# Grab allocation list from API
try:
    query_args = {
        'format':'json',
    }
    data = urllib.urlencode(query_args)
    url = '{}?{}'.format(settings.ALLOC_URL,data)
    req = urllib2.Request(url)
    res = urllib2.urlopen(req)
    res_json = res.read()

    allocations = json.loads(res_json)

except Exception as e:
    err_msg = 'Error while querying API.\n{}\n'.format(e)
    exit_with_msg(err_msg)

for alloc in allocations:
    proj_id = alloc['project']['project_id']
    parent = get_top_level(alloc)

    # Check if allocation/account exists in Slurm
    # otherwise add account to Slurm.
    if alloc['project']['project_id'] not in slurm_state:
        qoses = 'qos=normal,long,debug'
        if alloc['project']['qos_addenda'] != '':
            'qos=normal,long,debug,{}'.format(alloc['project']['qos_addenda'])
        cmd = [
            'sacctmgr',
            'add',
            '-i',
            'account',
            proj_id,
            'parent={}'.format(parent),
            '{}={}'.format(AMOUNT,alloc['amount']),
            'defaultqos=normal',
            qoses,
            'where',
            CLUSTER,
        ]
        output = run_slurm_cmd(cmd)

        # Add the newly-created account to slurm state and continue.
        cmd = [
            'sacctmgr',
            'show',
            'ass',
            FORMAT,
            CLUSTER,
            '-n',
            '-P',
            'account={}'.format(proj_id),
        ]
        output = run_slurm_cmd(cmd, exit_on_failure=True)
        parsed = output.split('|')
        d = {
            'users': [],
            'maxjobs': parsed[2],
            'qos': parsed[3],
            AMOUNT: parsed[4],
        }
        slurm_state[parsed[0]] = d

    # Determine whether or not the account is expired
    # or deactivated. If it is, set max_jobs=0.
    disable = False
    if alloc['project']['deactivated']:
        disable = True
    now = datetime.datetime.now()
    sdate = datetime.datetime.strptime(alloc['start_date'],'%Y-%m-%d')
    edate = datetime.datetime.strptime(alloc['end_date'],'%Y-%m-%d')
    if not sdate < now < edate:
        disable = True

    if disable:
        cmd = [
            'sacctmgr',
            '-i',
            'update',
            'account',
            proj_id,
            'set',
            'maxjobs=0',
            CLUSTER,
        ]
        output = run_slurm_cmd(cmd)
    elif (not disable) and (slurm_state[proj_id]['maxjobs'] == '0'):
        cmd = [
            'sacctmgr',
            '-i',
            'update',
            'account',
            proj_id,
            'set',
            'maxjobs=-1',
            CLUSTER,
        ]
        output = run_slurm_cmd(cmd)

    # Add/remove users from allocation/account
    #
    pusers = ast.literal_eval(alloc['project']['collaborators'])
    susers = slurm_state[proj_id]['users']
    # Compute adds
    adds = set(pusers) - set(susers)
    # Compute removes
    removes = set(susers) - set(pusers)
    if len(adds) > 0:
        cmd = [
            'sacctmgr',
            '-i',
            'add',
            'user',
            ','.join(adds),
            'account={}'.format(proj_id),
            CLUSTER,
        ]
        if proj_id in GENERAL_ACCOUNTS:
            def_acct = 'defaultaccount={}'.format(proj_id)
            cmd.append(def_acct)
        output = run_slurm_cmd(cmd)
    if len(removes) > 0:
        cmd = [
            'sacctmgr',
            '-i',
            'remove',
            'user',
            ','.join(removes),
            'account={}'.format(proj_id),
            CLUSTER,
        ]
        output = run_slurm_cmd(cmd)
