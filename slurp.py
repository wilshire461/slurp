import sys
import urllib.parse
import urllib.request
import json
import datetime
import subprocess

import settings



# Max errors that can be encountered before slurp exits
ERROR_THRESHOLD = 10
err_cnt = 0

def exit_with_msg(err_msg):
    err_msg_ts = '{}: {}\n'.format(datetime.datetime.now(),err_msg)
    sys.stderr.write(err_msg_ts)
    sys.exit(1)

def log_error(err_msg):
    err_cnt += 1
    err_msg_ts = '{}: {}\n'.format(datetime.datetime.now(),err_msg)
    sys.stderr.write(err_msg_ts)
    if err_cnt > ERROR_THRESHOLD:
        emsg = "Too many failures encountered, exiting...\n"
        exit_with_msg(emsg)

# Grab allocation list from API
try:
    query_args = {
        'format':'json',
    }
    data = urllib.parse.urlencode(query_args)
    url = '{}?{}'.format(settings.ALLOC_URL,data)
    req = urllib.request.Request(url)
    res = urllib.request.urlopen(req)
    res_json = res.read()

    allocations = json.loads(res_json.decode('utf-8'))

except Exception as e:
    err_msg = 'Error while querying API.\n{}\n'.format(e)
    exit_with_msg(err_msg)

for alloc in allocations:
    # Check if allocation/account exists in Slurm
    # otherwise add account to Slurm.
    #
    # sacctmgr show account <account_name>
    try:
        cmd = ['sacctmgr','show','account',alloc['allocation_id']]
        p = subprocess.run(cmd,check=True)

    except FileNotFoundError:
        err_msg = "Slurm not found! Exiting...\n"
        exit_with_msg(err_msg)

    except subprocess.CalledProcessError as e:
        err_msg = 'Command error: {}\n{}\n'.format(e.cmd,e.output)
        log_error(err_msg)
