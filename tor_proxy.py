import os
import re
import json
import termcolor
import requests
from datetime import datetime

import stem.process
from stem.control import Controller
from stem import Signal
from stem import CircStatus


OS = ''

if os.name == 'nt':
      OS = 'windows'
else:
      OS = 'posix'


SOCK_PORT    = 9050
CONTROL_PORT = 9051
TOR_PATH     = os.path.normpath(os.path.join(os.path.dirname(__file__), 'tor', OS, 'tor'))
TOR_DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), 'data', 'tor'))


class TorProxy(object):
      def __init__(self, tor_path, tor_data_dir, tor_control_port, tor_socks_port):
            self.tor_path = tor_path
            self.tor_data_dir = tor_data_dir
            self.tor_control_port = tor_control_port
            self.tor_socks_port = tor_socks_port
            self.tor_process = None
            self.tor_controller = None
            self.tor_session = None
            self.tor_session = requests.session()
            self.tor_session.proxies = {'http': 'socks5h://localhost:{}'.format(self.tor_socks_port), 
                                        'https': 'socks5h://localhost:{}'.format(self.tor_socks_port)}
            
      def __enter__(self):
            self.start_tor()
            return self.tor_session
      
      def __exit__(self, exc_type, exc_value, traceback):
            self.stop_tor()

      # Start TOR process
      def start_tor(self):
            self.tor_process = stem.process.launch_tor_with_config(
                  config = {
                        'SocksPort': str(self.tor_socks_port),
                        'ControlPort': str(self.tor_control_port),
                        'DataDirectory': self.tor_data_dir,
                        'CookieAuthentication': '1',
                        'MaxCircuitDirtiness': '60',
                        #'EntryNodes': 'CBCC85F335E20705F791CFC8685951C90E24134D',
                        'StrictNodes': '1',      # TOR connection shall strictly follow user configuration
                  },

                  tor_cmd = self.tor_path,
                  init_msg_handler = lambda line: print(line) if re.search('Bootstrapped', line) else False
            )

      # Prints all the circuits generated by TOR
      def showCircuits(self):
            with Controller.from_port(port = self.tor_control_port) as controller:
                  controller.authenticate()
                  
                  for circuit in controller.get_circuits():
                        if circuit.status == CircStatus.BUILT:

                              # Print all the circuits
                              print("\nCircuit %s (%s)" % (circuit.id, termcolor.colored(circuit.purpose, "green")))
                              
                              for i, entry in enumerate(circuit.path):
                                    div = '+' if (i == len(circuit.path) - 1) else '|'
                                    fingerprint, nickname = entry
                                    desc = controller.get_network_status(fingerprint, None)
                                    address = desc.address if desc else 'unknown'
                                    print(" %s- %s (%s, %s)" % (div, fingerprint, termcolor.colored(nickname, "green"), termcolor.colored(address, "yellow")))

      # Renew TOR circuit
      def renew_tor(self):
            with Controller.from_port(port = self.tor_control_port) as controller:
                  controller.authenticate()
                  controller.signal(Signal.NEWNYM)

      # Stop TOR process
      def stop_tor(self):
            self.tor_process.kill()

      # Show TOR connection status
      def showConnectionStatus(self):
            print("\nCONNECTION INFO:")
            self.showCircuits()
            response = self.tor_session.get('http://ip-api.com/json')
            result = json.loads(response.text)
            print('\nConnection status: {}'.format(termcolor.colored('OK', "green") if result['status'] == 'success' else termcolor.colored('FAILED', 'red')))
            print('IP: {}'.format(termcolor.colored(result['query'], "yellow")))
            print('Location: {}, {}'.format(result['city'], result['country']))
            print('ISP: {}'.format(result['isp']))
      
      def get(self, url):
            return self.tor_session.get(url)
      
      def post(self, url, data):
            return self.tor_session.post(url, data = data)


def testConnection(proxy):
      if proxy.get('https://google.com').status_code == 200:
            return True


if __name__ == '__main__':
      tp = TorProxy(tor_path = TOR_PATH, tor_data_dir = TOR_DATA_DIR, tor_control_port = CONTROL_PORT, tor_socks_port = SOCK_PORT)
      with tp:
            if testConnection(tp.tor_session):
                  tp.showConnectionStatus()

