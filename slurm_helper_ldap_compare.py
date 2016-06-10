#!/usr/bin/env python

# Compare lists and return differences
import grp
from subprocess import Popen, PIPE
# Set up LDAP group mapping
d = { 'acct1': 'ldap_acct1'}

for k in d:
    ldap = set(grp.getgrnam(d[k])[3])
    cmd = ['sacctmgr','-P','-n','show','account',k,'withassoc','format=user']
    p = Popen(cmd,stdout=PIPE)
    l = p.communicate()
    m = str(l).strip().replace('\\n','\n').split()
    slurm = set(m) - set(["('", 'None)',',',"',"])

    slurm_only = slurm - ldap
    ldap_only = ldap - slurm

    # Remove users from slurm
    print("I would remove these users from %s" % k)
    for U in slurm_only:
        #sacctmgr --immediate delete user name=$U account=$A
        print(U)

    # Add users to slurm
    print("I would add these users to %s:" % k)
    for U in ldap_only:
        #sacctmgr --immediate create user name=$U account=$A 
        print(U)
    print
