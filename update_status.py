import json
import sys
import time
import configparser
from urlparse import urlparse as parse
from datetime import datetime
import requests

class UptimeRobot(object):
    """ Intermediate class for setting uptime stats.
    """
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = 'https://api.uptimerobot.com/'

    def get_monitors(self, response_times=0, logs=0, uptime_ratio=30):
        """
        Returns status and response payload for all known monitors.
        """
        url = self.base_url
        url += 'getMonitors?apiKey={0}'.format(self.api_key)
        url += '&noJsonCallback=1&format=json'

        # responseTimes - optional (defines if the response time data of each
        # monitor will be returned. Should be set to 1 for getting them.
        # Default is 0)
        url += '&responseTimes={0}'.format(response_times)

        # logs - optional (defines if the logs of each monitor will be
        # returned. Should be set to 1 for getting the logs. Default is 0)
        url += '&logs={0}'.format(logs)

        # customUptimeRatio - optional (defines the number of days to calculate
        # the uptime ratio(s) for. Ex: customUptimeRatio=7-30-45 to get the
        # uptime ratios for those periods)
        url += '&customUptimeRatio={0}'.format(uptime_ratio)

        # Verifying in the response is jsonp in otherwise is error
        response = requests.get(url=url)
        content = response.text
        j_content = response.json()

        if j_content.get('stat'):
            stat = j_content.get('stat')
            if stat == 'ok':
                return True, j_content

        return False, j_content

class CachetHq(object):
    # Uptime Robot status list
    UPTIME_ROBOT_PAUSED = 0
    UPTIME_ROBOT_NOT_CHECKED_YET = 1
    UPTIME_ROBOT_UP = 2
    UPTIME_ROBOT_SEEMS_DOWN = 8
    UPTIME_ROBOT_DOWN = 9

    # Cachet status list
    CACHET_OPERATIONAL = 1
    CACHET_PERFORMANCE_ISSUES = 2
    CACHET_SEEMS_DOWN = 3
    CACHET_DOWN = 4

    def __init__(self, cachet_api_key, cachet_url):
        self.cachet_api_key = cachet_api_key or CACHET_API_KEY
        self.cachet_url = cachet_url or CACHET_URL

    def update_component(self, id_component=1, status=None):
        component_status = None

        # Not Checked yet and Up
        if status in [self.UPTIME_ROBOT_NOT_CHECKED_YET, self.UPTIME_ROBOT_UP]:
            component_status = self.CACHET_OPERATIONAL

        # Seems down
        elif status == self.UPTIME_ROBOT_SEEMS_DOWN:
            component_status = self.CACHET_SEEMS_DOWN

        # Down
        elif status == self.UPTIME_ROBOT_DOWN:
            component_status = self.CACHET_DOWN

        if component_status:
            url = '{0}/api/v1/{1}/{2}/'.format(
                self.cachet_url,
                'components',
                id_component
            )
            data = {'status': component_status}
            headers={'X-Cachet-Token': CACHET_API_KEY}
            response = requests.put(url=url, data=data, headers=headers)
            content = response.text
            return content

    def set_data_metrics(self, value, timestamp, id_metric=1):
        url = '{0}/api/v1/metrics/{1}/points/'.format(
            CACHET_URL,
            id_metric
        )

        data = {'value': value,'timestamp': timestamp}
        headers={'X-Cachet-Token': CACHET_API_KEY}
        response = requests.post(url=url, data=data, headers=headers)
        content = response.text
        return response.json()

    def get_last_metric_point(self, id_metric):
        url = '{0}/api/v1/metrics/{1}/points/'.format(
            self.cachet_url,
            id_metric
        )
        headers={'X-Cachet-Token': CACHET_API_KEY}
        response = requests.get(url=url, headers=headers)
        content = response.text

        last_page = json.loads(
            content
        ).get('meta').get('pagination').get('total_pages')

        url = '{0}/api/v1/metrics/{1}/points?page={2}'.format(
            self.cachet_url,
            id_metric,
            last_page
        )

        response = requests.get(url=url, headers={'X-Cachet-Token': CACHET_API_KEY})
        content = response.text

        if json.loads(content).get('data'):
            data = json.loads(content).get('data')[0]
        else:
            data = {
                'created_at': datetime.now().date().strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
            }

        return data

class Monitor(object):
    def __init__(self, monitor_list, api_key):
        self.monitor_list = monitor_list
        self.api_key = api_key

    def send_data_to_cachet(self, monitor):
        """ Posts data to Cachet API.
            Data sent is the value of last `Uptime`.
        """
        try:
            website_config = self.monitor_list[monitor.get('url')]
        except KeyError:
            print('ERROR: monitor is not valid')
            sys.exit(1)

        cachet = CachetHq(
            cachet_api_key=CACHET_API_KEY,
            cachet_url=CACHET_URL,
        )

        if 'component_id' in website_config:
            cachet.update_component(
                website_config['component_id'],
                int(monitor.get('status'))
            )

        metric = cachet.set_data_metrics(
            monitor.get('customuptimeratio'),
            int(time.time()),
            website_config['metric_id']
        )
        print('Metric created: {0}'.format(metric))

    def update(self):
        """ Update all monitors uptime and status.
        """
        uptime_robot = UptimeRobot(self.api_key)
        success, response = uptime_robot.get_monitors(response_times=1)
        if success:
            monitors = response.get('monitors').get('monitor')
            for monitor in monitors:
                if monitor['url'] in self.monitor_list:
                    print('Updating monitor {0}. URL: {1}. ID: {2}'.format(
                        monitor['friendlyname'],
                        monitor['url'],
                        monitor['id'],
                    ))
                    self.send_data_to_cachet(monitor)
        else:
            print('ERROR: No data was returned from UptimeMonitor')

if __name__ == "__main__":
    CONFIG = configparser.ConfigParser()
    CONFIG.read(sys.argv[1])
    SECTIONS = CONFIG.sections()

    if not SECTIONS:
        print('ERROR: File path is not valid')
        sys.exit(1)

    UPTIME_ROBOT_API_KEY = None
    CACHET_API_KEY = None
    CACHET_URL = None
    MONITOR_DICT = {}
    for element in SECTIONS:
        if element == 'uptimeRobot':
            uptime_robot_api_key = CONFIG[element]['UptimeRobotMainApiKey']
        elif element == 'cachet':
            CACHET_API_KEY = CONFIG[element]['CachetApiKey']
            CACHET_URL = CONFIG[element]['CachetUrl']
        else:
            MONITOR_DICT[element] = {
                'cachet_api_key': CONFIG[element]['CachetApiKey'],
                'cachet_url': CONFIG[element]['CachetUrl'],
                'metric_id': CONFIG[element]['MetricId'],
            }
            if 'ComponentId' in CONFIG[element]:
                MONITOR_DICT[element].update({
                    'component_id': CONFIG[element]['ComponentId'],
                })

    MONITOR = Monitor(monitor_list=MONITOR_DICT, api_key=uptime_robot_api_key)
    MONITOR.update()
