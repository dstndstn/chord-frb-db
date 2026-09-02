
class Actor(object):

    def __init__(self, **kwargs):
        pass

    def perform_action(self, event_group):
        try:
            return self._perform_action(event_group)
        except:
            import traceback
            traceback.print_exc()
            raise

    def _perform_action(self, event_group):
        raise RuntimeError('not implemented')

    def shutdown(self):
        pass
