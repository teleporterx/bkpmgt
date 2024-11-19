# srvr/backup_recovery/__init__.py

# docstring
"""
<info>
"""

from .mutations import BackupMutations # will possibly trigger a circular import issue if comms.conn_manager calls this
from .queries import BackupQueries # will possibly trigger a circular import issue if comms.conn_manager calls this

"""
do not use
```
from backup_recovery import <function>
```
in conn_manager, as it will lead to circular import error.

rather use 
```
from backup_recovery.<module> import <function>
```
"""
__version__ = "1.0.0"