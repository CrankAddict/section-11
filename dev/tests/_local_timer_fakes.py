"""In-memory cron transport: legacy installer tests never inspect host timers."""
from types import SimpleNamespace


def fake_timers(real_class):
    class FakeTimers(real_class):
        crontabs = {}

        def __init__(self, data_dir, **kwargs):
            super().__init__(data_dir, home=data_dir / 'synthetic-home', platform='test-cron')

        def command(self, argv, input=None):
            key = str(self.root)
            if argv == ['crontab', '-l']:
                value = self.crontabs.get(key)
                return SimpleNamespace(returncode=0 if value is not None else 1,
                                       stdout=value or '', stderr='' if value is not None else 'no crontab')
            if argv == ['crontab', '-']:
                self.crontabs[key] = input
            elif argv == ['crontab', '-r']:
                self.crontabs.pop(key, None)
            else:
                raise AssertionError('unmocked scheduler command: ' + repr(argv))
            return SimpleNamespace(returncode=0, stdout='', stderr='')
    return FakeTimers
