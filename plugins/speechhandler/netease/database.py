import yaml
import logging
import os
import ConfigParser
from jasper import paths

NETEASE_CFG_PATH = os.path.join(paths.PLUGIN_PATH, 'speechhandler/netease')

class Database(object):
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._config = ConfigParser.ConfigParser()

    def load(self):
        # Check if netease plugin dir is writable
        if not os.access(NETEASE_CFG_PATH, os.W_OK):
            self._logger.critical("Netease plugin dir %s is not writable. Jasper " +
                    "won't work correctly.",
                    NETEASE_CFG_PATH)
            return

        self._cfgfile = os.path.join(NETEASE_CFG_PATH, 'netease.yml')

        self._logger.debug("Trying to read Netease plugin config file: netease.yml")

        try:
            with open(self._cfgfile, "r") as f:
                self._config = yaml.safe_load(f)
                f.close()
        except IOError:
            f = open(self._cfgfile, 'w')
            self._config = {}
            f.close()
        except OSError:
            self._logger.error("Can't open Netease plugin config file: '%s'", cfgfile)
            raise
        except (yaml.parser.ParserError, yaml.scanner.ScannerError) as e:
            self._logger.error("Unable to parse Netease plugin config file: %s %s",
                    e.problem.strip(), str(e.problem_mark).strip())
            raise

    def getUserId(self):
        try:
            userid = self._config['userid']
            return userid
        except Exception:
            return ''

    def setUserId(self, userid):
        try:
            self._config['userid'] = userid
        except TypeError:
            self._config={'userid':userid}
        try:
            with file(self._cfgfile, 'w') as f:
                yaml.dump(self._config, f)
        except IOError as e:
            self._logger.error(e)
        finally:
            f.close()

