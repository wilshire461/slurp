# slurp
Slurp is a Slurm state manager. Slurp pulls from RCAMP and LDAP, and reconciles that data into Slurm state.

Usage:

DO NOT EDIT settings.py, instead create a file called local_settings.py and fill it with the variables you want to change

Variables:

ALLOC_URL
This variable tells slurp where to go to grab allocation data from the RCAMP API.

CLUSTER_NAME
This variable tells slurp which cluster within slurm to grab and edit data for.

AMOUNT_ATTRIBUTE
This variable tells slurp how the time is being interpreted.
