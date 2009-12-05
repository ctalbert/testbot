import os
import sys
from time import sleep
from threading import Thread
from httplib2 import Http

try:
    import json
except:
    import simplejson as json

http = Http()

class ClientException(Exception): pass

class JobException(Exception): pass

print "client.py is loaded"

class Client(object):
    heartbeat_interval = 60
    waiting_sleep = 60
    jobtypes = []
    device = {}
    
    def __init__(self, server_uri, name):
        print "client init is beginning"
        if not server_uri.endswith('/'):
            server_uri += '/'
        self.server_uri = server_uri
        self.name = name
        self.registered = False
        self.running = False
        self.heartbeat_running = False
        print "client init is finishing"
    
    def register(self):
        print "client reigister is beginning"
        resp, content = http.request(self.server_uri+'api/whoami?name='+self.name, method="GET")
        if resp.status == 200:
            self.client_info = json.loads(content)
            self.client_info['capabilities'] = self.capabilities
            self.client_info['heartbeat_interval'] = self.heartbeat_interval
            self.registered = True
        else:
            raise ClientException("Whoami failed for name "+self.name+'\n'+content)
    
    @property
    def capabilities(self):
        print "capapbilities is being accessed"
        return {'platform':self.platform, 'jobtypes':self.jobtypes, 'device':self.device}
    
    @property
    def platform(self):
        sysname, nodename, release, version, machine = os.uname()
        sysinfo = {'os.sysname':sysname, 'os.hostname':nodename, 'os.version.number':release,
                   'os.version.string':version, 'os.arch':machine}
        if sys.platform == 'darwin':
            import platform
            sysinfo['os.mac.version'] = platform.mac_ver()
        elif sys.platform == 'linux':
            import platform
            sysinfo['os.linux.distribution'] = platform.linux_distribution()
            sysinfo['os.libc.ver'] = platform.libc_ver()
        return sysinfo
        
    def get_job(self):
        print "get_job uri = " + self.server_uri + 'api/getJob'
        resp, content = http.request(self.server_uri+'api/getJob', method='POST', body=json.dumps(self.client_info))
        assert resp
        if resp.status == 200:
            job = json.loads(content)
            self.client_info['job'] = job
            return job
        elif resp.status == 204:
            return None
        else:
            raise ClientException("getJob failed \n"+content) 
        
    def run(self):
        if self.registered is False:
            self.register()
        self.client_info['status'] = 'available'
        self.start_heartbeat()
        self.running = True
        while self.running is True:
            job = self.get_job()
            if job is None:
                sleep(self.waiting_sleep)
            else:
                self.client_info['status'] = 'busy'
                self.push_status()
                result = self._do_job(job)
                if type(result) != JobException:
                    self.report(job, result)
                self.client_info['status'] = 'available'
                self.push_status()
    
    def heartbeat(self):
        assert self.heartbeat_running is False
        while self.heartbeat_running:
            self.push_status()
            sleep(self.heartbeat_interval)
    
    def start_heartbeat(self):
        self.heartbeat_thread = Thread(target=self.heartbeat)
        self.heartbeat_thread.start()
        return self.heartbeat_thread
    
    def stop_heartbeat(self):
        while self.heartbeat_thread.isAlive():
            self.heartbeat_running = False
            sleep(self.heartbeat_interval / 4)    
    
    def push_status(self):
        resp, content = http.request(self.server_uri+'api/heartbeat/'+self.client_info['_id'], method='POST', body=json.dumps(self.client_info))
        assert resp.status == 200
        info = json.loads(content)
        self.client_info['_rev'] = info['rev']
    
    def report(self, job, result):
        resp, content = http.request(self.server_uri+'api/report/'+job['_id'], method='POST', body=json.dumps(result))
        assert resp.status == 200
        if not content:
            return None
        return json.loads(content)
    
    def _do_job(self, job):
        if not hasattr(self, 'do_job'):
            raise NotImplemented("You must implement a client.do_job function()")
        try:
            return self.do_job(job)
        except:
            pass # TODO: Exception handling
    
    def start(self):
        self.thread = Thread(target=self.run)
        self.thread.start()
        return self.thread
    
    def stop(self):
        while self.thread.isAlive():
            self.running = False
            sleep(self.waiting_sleep / 4)
        
