ALLOC_URL = 'http://localhost:8000/api/allocations/'
CLUSTER_NAME = 'slurmdev'
AMOUNT_ATTRIBUTE = 'grpcpumins'

try:
    from local_settings import *
except:
    pass
