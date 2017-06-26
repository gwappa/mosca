
from . import models

##
## Message-manager class
##

class MessageManager(models.SingletonManager):

    @models.ensure_singleton
    def warn_revert(cls, title, msg):
        print("***{0}: ".format(title)+msg)
        # ViewManager.show_warning(title, msg)

    @models.ensure_singleton
    def not_implemented(cls, title, msg):
        print("***{0}: {1}".format(title, msg))
